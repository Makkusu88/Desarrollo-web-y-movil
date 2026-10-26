import json
import sys
import time
import uuid
from pathlib import Path

import httpx
import psutil
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from common.config import PUERTOS, RUNTIME_DIR  # noqa: E402

GATEWAY = f"http://127.0.0.1:{PUERTOS['gateway']}"
API = f"{GATEWAY}/api/v1"
SEED = json.loads((RAIZ / "scripts" / "seed_data.json").read_text(encoding="utf-8"))
USUARIOS = {u["email"].split("@")[0]: u for u in SEED["usuarios"]}  # admin, cocina, ana, pedro


def pytest_configure(config):
    try:
        httpx.get(f"{GATEWAY}/health", timeout=2).raise_for_status()
    except Exception:  # noqa: BLE001
        pytest.exit("El sistema no está en ejecución. Inicia: python run_all.py --reset --ttl-pago 30", returncode=2)


@pytest.fixture(scope="session")
def http():
    # Sin cookies persistentes: cada prueba envía su token explícitamente.
    with httpx.Client(base_url=API, timeout=20, cookies=None) as cliente:
        yield cliente


def login(email: str, password: str) -> dict:
    r = httpx.post(f"{API}/auth/login", json={"email": email, "password": password},
                   headers={"X-Token-Delivery": "body"}, timeout=10)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def tokens():
    return {nombre: login(u["email"], u["password"]) for nombre, u in USUARIOS.items()}


@pytest.fixture(scope="session")
def secretos_pruebas():
    token = (RUNTIME_DIR / "pruebas.token").read_text(encoding="utf-8").strip()
    r = httpx.get(f"http://127.0.0.1:{PUERTOS['vault']}/v1/secret/data/mrsandwich/pruebas",
                  headers={"X-Vault-Token": token}, timeout=5)
    r.raise_for_status()
    return r.json()["data"]["data"]


def gql(http, headers, query, variables=None):
    return http.post("/graphql", headers=headers, json={"query": query, "variables": variables or {}})


def stock_de(http, headers_admin, producto_id: int) -> int:
    productos = http.get("/admin/products", headers=headers_admin).json()
    return next(p["stock"] for p in productos if p["id"] == producto_id)


def crear_pedido(http, headers, items, tipo="RETIRO", direccion_id=None, clave=None):
    cab = dict(headers)
    if clave:
        cab["Idempotency-Key"] = clave
    return http.post("/orders", headers=cab, json={"items": items, "tipo_entrega": tipo, "direccion_id": direccion_id})


def pagar_y_resolver(http, headers, order_id: str, aprobar=True) -> dict:
    pago = http.post("/payments", headers=headers, json={"order_id": order_id})
    assert pago.status_code == 201, pago.text
    sesion = pago.json()["checkout_url"].rsplit("/", 1)[1]
    accion = "approve" if aprobar else "reject"
    r = httpx.post(f"http://127.0.0.1:{PUERTOS['provider']}/checkout/{sesion}/{accion}", follow_redirects=False)
    assert r.status_code == 303
    return {**pago.json(), "sesion": sesion}


def esperar(condicion, segundos=30, intervalo=1.0):
    limite = time.time() + segundos
    while time.time() < limite:
        valor = condicion()
        if valor:
            return valor
        time.sleep(intervalo)
    return None


class ProcesoSuspendido:

    def __init__(self, nombre: str):
        pids = json.loads((RUNTIME_DIR / "pids.json").read_text(encoding="utf-8"))
        raiz = psutil.Process(pids[nombre])
        # En Windows el python.exe del venv es un lanzador: el servicio corre en un proceso hijo.
        self.procesos = [raiz, *raiz.children(recursive=True)]

    def __enter__(self):
        for p in self.procesos:
            p.suspend()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.procesos):
            p.resume()


@pytest.fixture
def email_unico():
    return f"prueba-{uuid.uuid4().hex[:8]}@cliente.test"
