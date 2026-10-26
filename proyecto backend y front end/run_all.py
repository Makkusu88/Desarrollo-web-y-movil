import argparse
import glob
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent
BACKEND = RAIZ / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(RAIZ / "scripts"))

from common.config import PUERTOS, RUNTIME_DIR  # noqa: E402
import bootstrap  # noqa: E402
import seed  # noqa: E402

LOGS = RUNTIME_DIR / "logs"
PIDS = RUNTIME_DIR / "pids.json"
VAULT_ADDR = f"http://127.0.0.1:{PUERTOS['vault']}"

# (nombre, módulo ASGI). El orden respeta dependencias de arranque.
SERVICIOS_PY = [
    ("inventory", "inventory_service.main:app"),
    ("clients", "clients_service.main:app"),
    ("auth", "auth_service.main:app"),
    ("orders", "orders_service.main:app"),
    ("payments", "payments_service.main:app"),
    ("analytics", "analytics_service.main:app"),
    ("provider", "provider_sim.main:app"),
]

procesos: list[tuple[str, subprocess.Popen]] = []


def info(msg: str):
    print(f"[run_all] {msg}", flush=True)


def ruta_mongod() -> str:
    candidato = os.getenv("MONGOD_PATH") or shutil.which("mongod")
    if not candidato:
        encontrados = sorted(glob.glob(r"C:\Program Files\MongoDB\Server\*\bin\mongod.exe"))
        candidato = encontrados[-1] if encontrados else None
    if not candidato:
        raise SystemExit("No se encontró mongod. Define MONGOD_PATH con la ruta a mongod.exe")
    return candidato


LINEAS_SENSIBLES = ("Root Token", "Unseal Key", "VAULT_TOKEN", "token_id")


def _filtrar_salida(origen, destino):
    for linea in iter(origen.readline, ""):
        if not any(s in linea for s in LINEAS_SENSIBLES):
            destino.write(linea)
            destino.flush()


def lanzar(nombre: str, cmd: list[str], env: dict | None = None, cwd: Path = BACKEND,
           filtrar: bool = False) -> subprocess.Popen:
    log = open(LOGS / f"{nombre}.log", "a", encoding="utf-8")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    p = subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **(env or {})},
                         stdout=subprocess.PIPE if filtrar else log, stderr=subprocess.STDOUT,
                         creationflags=flags, text=filtrar, encoding="utf-8" if filtrar else None,
                         errors="replace" if filtrar else None)
    if filtrar:
        threading.Thread(target=_filtrar_salida, args=(p.stdout, log), daemon=True).start()
    procesos.append((nombre, p))
    return p


def esperar(nombre: str, comprobar, segundos: int = 30):
    limite = time.time() + segundos
    while time.time() < limite:
        proc = dict(procesos).get(nombre)
        if proc and proc.poll() is not None:
            raise SystemExit(f"{nombre} terminó al iniciar. Revisa {LOGS / (nombre + '.log')}")
        try:
            if comprobar():
                return
        except Exception:  # noqa: BLE001 - aún no responde
            pass
        time.sleep(0.4)
    raise SystemExit(f"{nombre} no respondió a tiempo. Revisa {LOGS / (nombre + '.log')}")


def http_ok(url: str):
    return lambda: httpx.get(url, timeout=1.0).status_code == 200


def puerto_libre(puerto: int) -> bool:
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", puerto)) != 0


def terminar_arbol(pid: int):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        subprocess.run(["kill", str(pid)], capture_output=True)


def detener_todo():
    for nombre, p in reversed(procesos):
        if p.poll() is not None:
            continue
        if nombre == "mongod":
            try:
                with bootstrap.cliente_admin(RUNTIME_DIR, PUERTOS["mongo"]) as c:
                    c.admin.command("shutdown")
            except Exception:  # noqa: BLE001 - mongod cierra la conexión al apagarse
                pass
            try:
                p.wait(timeout=15)
                continue
            except subprocess.TimeoutExpired:
                pass
        terminar_arbol(p.pid)
    for _, p in procesos:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
    PIDS.unlink(missing_ok=True)
    info("Sistema detenido.")


def detener_externo():
    if not PIDS.exists():
        raise SystemExit("No hay un sistema registrado en ejecución.")
    datos = json.loads(PIDS.read_text(encoding="utf-8"))
    try:
        with bootstrap.cliente_admin(RUNTIME_DIR, PUERTOS["mongo"]) as c:
            c.admin.command("shutdown")
    except Exception:  # noqa: BLE001
        pass
    for nombre, pid in reversed(list(datos.items())):
        if nombre == "mongod":
            continue
        terminar_arbol(pid)
    PIDS.unlink(missing_ok=True)
    info("Sistema detenido.")


def iniciar(args):
    for d in (RUNTIME_DIR, LOGS, RUNTIME_DIR / "mongo-data", RUNTIME_DIR / "outbox"):
        d.mkdir(parents=True, exist_ok=True)
    ocupados = [n for n in ("gateway", "auth", "clients", "inventory", "orders", "payments", "analytics", "graphql",
                            "provider", "frontend", "vault", "mongo", "inventory_grpc") if not puerto_libre(PUERTOS[n])]
    if ocupados:
        raise SystemExit(f"Puertos ocupados: {', '.join(f'{n}:{PUERTOS[n]}' for n in ocupados)}. "
                         "¿Ya hay una instancia corriendo? Usa 'python run_all.py stop'.")

    info("Iniciando MongoDB (con autenticación)...")
    lanzar("mongod", [ruta_mongod(), "--dbpath", str(RUNTIME_DIR / "mongo-data"), "--port", str(PUERTOS["mongo"]),
                      "--bind_ip", "127.0.0.1", "--auth", "--quiet"])
    from pymongo import MongoClient
    esperar("mongod", lambda: MongoClient(f"mongodb://127.0.0.1:{PUERTOS['mongo']}/?directConnection=true",
                                          serverSelectionTimeoutMS=500).admin.command("ping"))

    info("Iniciando Vault (modo desarrollo, en memoria)...")
    token_raiz = secrets.token_urlsafe(24)
    lanzar("vault", ["vault", "server", "-dev", f"-dev-root-token-id={token_raiz}",
                     f"-dev-listen-address=127.0.0.1:{PUERTOS['vault']}", "-dev-no-store-token"], filtrar=True)
    esperar("vault", http_ok(f"{VAULT_ADDR}/v1/sys/health"))

    info("Bootstrap: rotando secretos, certificados y usuarios de base de datos...")
    tokens = bootstrap.ejecutar(VAULT_ADDR, token_raiz, RUNTIME_DIR, PUERTOS["mongo"])
    del token_raiz  # el token raíz no se entrega a ningún servicio
    # Token exclusivo de la suite de pruebas (política: solo mrsandwich/pruebas).
    (RUNTIME_DIR / "pruebas.token").write_text(tokens.pop("pruebas"), encoding="utf-8")

    with bootstrap.cliente_admin(RUNTIME_DIR, PUERTOS["mongo"]) as c:
        acciones = seed.ejecutar(c, reiniciar=args.reset)
    if acciones:
        info("Datos de prueba: " + ", ".join(acciones))

    base_env = {"VAULT_ADDR": VAULT_ADDR, "PYTHONPATH": str(BACKEND), "MRSANDWICH_RUNTIME": str(RUNTIME_DIR),
                "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    if args.ttl_pago:
        base_env["ORDER_PAYMENT_TTL_SECONDS"] = str(args.ttl_pago)

    for nombre, modulo in SERVICIOS_PY:
        info(f"Iniciando {nombre} en 127.0.0.1:{PUERTOS[nombre]}")
        lanzar(nombre, [sys.executable, "-m", "uvicorn", modulo, "--host", "127.0.0.1", "--port", str(PUERTOS[nombre]),
                        "--no-access-log", "--log-level", "warning"], {**base_env, "VAULT_TOKEN": tokens[nombre]})
        esperar(nombre, http_ok(f"http://127.0.0.1:{PUERTOS[nombre]}/health"))

    info(f"Iniciando GraphQL Gateway privado en 127.0.0.1:{PUERTOS['graphql']}")
    lanzar("graphql", ["node", "src/index.js"], {"VAULT_ADDR": VAULT_ADDR, "VAULT_TOKEN": tokens["graphql"]},
           cwd=BACKEND / "graphql_gateway")
    esperar("graphql", lambda: not puerto_libre(PUERTOS["graphql"]))

    env_gateway = {**base_env, "VAULT_TOKEN": tokens["gateway"]}
    if args.perfil == "carga":
        env_gateway.update(RATE_GENERAL="1000000", RATE_SENSIBLE="1000000", RATE_GRAPHQL="1000000")
    info(f"Iniciando API Gateway en 127.0.0.1:{PUERTOS['gateway']}")
    lanzar("gateway", [sys.executable, "-m", "uvicorn", "api_gateway.main:app", "--host", "127.0.0.1",
                       "--port", str(PUERTOS["gateway"]), "--no-access-log", "--log-level", "warning"], env_gateway)
    esperar("gateway", http_ok(f"http://127.0.0.1:{PUERTOS['gateway']}/health"))

    info(f"Sirviendo frontend en http://localhost:{PUERTOS['frontend']}")
    lanzar("frontend", [sys.executable, "-m", "http.server", str(PUERTOS["frontend"]), "--bind", "127.0.0.1",
                        "--directory", str(RAIZ / "frontend")])
    esperar("frontend", http_ok(f"http://127.0.0.1:{PUERTOS['frontend']}/index.html"))

    PIDS.write_text(json.dumps({n: p.pid for n, p in procesos}), encoding="utf-8")
    info("Sistema listo.")
    info(f"  Frontend:    http://localhost:{PUERTOS['frontend']}")
    info(f"  API Gateway: http://localhost:{PUERTOS['gateway']}/api/v1/...")
    info(f"  Logs:        {LOGS}")
    info("Ctrl+C para detener.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("accion", nargs="?", default="start", choices=["start", "stop"])
    parser.add_argument("--reset", action="store_true", help="reinicia las bases con los datos de prueba")
    parser.add_argument("--perfil", choices=["normal", "carga"], default="normal")
    parser.add_argument("--ttl-pago", type=int, help="segundos para pagar un pedido antes de que expire")
    args = parser.parse_args()

    if args.accion == "stop":
        detener_externo()
        return
    try:
        iniciar(args)
        while all(p.poll() is None for _, p in procesos):
            time.sleep(1)
        caidos = [n for n, p in procesos if p.poll() is not None]
        info(f"Proceso detenido inesperadamente: {', '.join(caidos)}. Revisa los logs.")
    except KeyboardInterrupt:
        pass
    finally:
        detener_todo()


if __name__ == "__main__":
    main()
