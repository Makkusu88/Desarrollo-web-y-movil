import argparse
import json
import platform
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import httpx
import psutil

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))
from common.config import PUERTOS, RUNTIME_DIR  # noqa: E402

API = f"http://127.0.0.1:{PUERTOS['gateway']}/api/v1"
SEED = json.loads((RAIZ / "scripts" / "seed_data.json").read_text(encoding="utf-8"))
ANA = next(u for u in SEED["usuarios"] if u["email"].startswith("ana@"))

# Objetivos declarados (ver ADR-02 en docs/INFORME.docx)
OBJETIVOS = {"E1 catálogo": 200, "E2 cotización (gRPC)": 300, "E3 agregación GraphQL": 500}  # p95 en ms
MAX_ERRORES = 0.01

CONSULTA = ("{ misPedidos(pagina: 1, tamano: 5) { total items { id estado total "
            "items { nombre producto { imagen disponible } } pago { estado } } } }")


def procesos_backend() -> list[psutil.Process]:
    pids = json.loads((RUNTIME_DIR / "pids.json").read_text(encoding="utf-8"))
    lista = []
    for nombre, pid in pids.items():
        if nombre in ("frontend",):
            continue
        raiz = psutil.Process(pid)
        lista.extend([raiz, *raiz.children(recursive=True)])
    return lista


def muestrear_recursos(procesos, detener: threading.Event, muestras: list):
    for p in procesos:
        p.cpu_percent(None)
    while not detener.wait(1):
        cpu = mem = 0.0
        for p in procesos:
            try:
                cpu += p.cpu_percent(None)
                mem += p.memory_info().rss
            except psutil.Error:
                pass
        muestras.append((cpu, mem / 1024 / 1024))


def escenario(nombre, hacer, concurrencia, duracion):
    latencias, errores, lock = [], [0], threading.Lock()
    fin = time.perf_counter() + duracion

    def trabajador():
        with httpx.Client(timeout=10) as cliente:
            while time.perf_counter() < fin:
                inicio = time.perf_counter()
                try:
                    r = hacer(cliente)
                    ok = r.status_code == 200 and '"errors"' not in r.text
                except httpx.HTTPError:
                    ok = False
                with lock:
                    latencias.append((time.perf_counter() - inicio) * 1000)
                    errores[0] += 0 if ok else 1

    detener, muestras = threading.Event(), []
    monitor = threading.Thread(target=muestrear_recursos, args=(procesos_backend(), detener, muestras))
    monitor.start()
    t0 = time.perf_counter()
    with ThreadPoolExecutor(concurrencia) as ejecutor:
        for _ in range(concurrencia):
            ejecutor.submit(trabajador)
    transcurrido = time.perf_counter() - t0
    detener.set()
    monitor.join()
    errores = errores[0]

    latencias.sort()
    pct = lambda q: latencias[min(len(latencias) - 1, int(len(latencias) * q))]  # noqa: E731
    return {
        "escenario": nombre, "concurrencia": concurrencia, "duracion_s": round(transcurrido, 1),
        "solicitudes": len(latencias), "throughput_rps": round(len(latencias) / transcurrido, 1),
        "errores": errores, "tasa_errores": round(errores / max(1, len(latencias)), 4),
        "p50_ms": round(pct(0.50), 1), "p95_ms": round(pct(0.95), 1), "p99_ms": round(pct(0.99), 1),
        "promedio_ms": round(statistics.fmean(latencias), 1),
        "cpu_promedio_pct": round(statistics.fmean(m[0] for m in muestras), 1) if muestras else None,
        "cpu_max_pct": round(max(m[0] for m in muestras), 1) if muestras else None,
        "memoria_max_mb": round(max(m[1] for m in muestras), 1) if muestras else None,
        "objetivo_p95_ms": OBJETIVOS[nombre],
    }


def main(concurrencia: int, duracion: int, etiqueta: str):
    r = httpx.post(f"{API}/auth/login", json={"email": ANA["email"], "password": ANA["password"]},
                   headers={"X-Token-Delivery": "body"})
    r.raise_for_status()
    cab = {"Authorization": f"Bearer {r.json()['access_token']}"}
    carrito = {"items": [{"product_id": 1, "option_id": "grande", "extras": [{"extra_id": "palta", "qty": 1}], "qty": 2},
                         {"product_id": 9, "option_id": "350", "qty": 1}]}

    escenarios = [
        ("E1 catálogo", lambda c: c.get(f"{API}/products")),
        ("E2 cotización (gRPC)", lambda c: c.post(f"{API}/orders/quote", json=carrito)),
        ("E3 agregación GraphQL", lambda c: c.post(f"{API}/graphql", headers=cab, json={"query": CONSULTA})),
    ]
    resultados = []
    for nombre, hacer in escenarios:
        print(f"Ejecutando {nombre} ({concurrencia} concurrentes, {duracion}s)...", flush=True)
        resultados.append(escenario(nombre, hacer, concurrencia, duracion))
        time.sleep(2)

    entorno = {
        "fecha": datetime.now().isoformat(timespec="seconds"), "so": platform.platform(),
        "cpu": platform.processor(), "nucleos_logicos": psutil.cpu_count(),
        "memoria_total_gb": round(psutil.virtual_memory().total / 1024 ** 3, 1),
        "python": platform.python_version(), "tipo": "medición (no proyección)",
        "datos": "seed_data.json (11 productos, 4 usuarios) + pedidos de las pruebas",
    }
    salida = RAIZ / "docs" / "evidencias"
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"prueba_carga_{etiqueta}.json").write_text(json.dumps({"entorno": entorno, "resultados": resultados}, indent=2,
                                                         ensure_ascii=False), encoding="utf-8")
    filas = "\n".join(
        f"| {r['escenario']} | {r['concurrencia']} | {r['solicitudes']} | {r['throughput_rps']} | {r['p50_ms']} | "
        f"{r['p95_ms']} | {r['p99_ms']} | {r['tasa_errores'] * 100:.2f}% | {r['cpu_promedio_pct']} / {r['cpu_max_pct']} | "
        f"{r['memoria_max_mb']} | {r['objetivo_p95_ms']} | "
        f"{'Cumple' if r['p95_ms'] <= r['objetivo_p95_ms'] and r['tasa_errores'] <= MAX_ERRORES else 'No cumple'} |"
        for r in resultados)
    (salida / f"prueba_carga_{etiqueta}.md").write_text(f"""# Prueba de carga ({etiqueta}) — resultados medidos

Entorno: {entorno['so']} · {entorno['nucleos_logicos']} núcleos lógicos · {entorno['memoria_total_gb']} GB RAM ·
Python {entorno['python']} · {entorno['fecha']}. Todos los componentes en el mismo PC (el generador de carga compite
por CPU con el backend, por lo que los valores son conservadores).

Tipo: **{entorno['tipo']}**. Comando: `python scripts/prueba_carga.py --concurrencia {concurrencia} --duracion {duracion} --etiqueta {etiqueta}`
con el sistema iniciado con `python run_all.py --reset --perfil carga`.

| Escenario | Concurrencia | Solicitudes | Throughput (req/s) | p50 ms | p95 ms | p99 ms | Errores | CPU backend % prom/máx | Memoria backend máx MB | Objetivo p95 ms | Resultado |
|---|---|---|---|---|---|---|---|---|---|---|---|
{filas}

CPU: suma de los procesos del backend (100 % = un núcleo completo). Memoria: RSS sumada de esos procesos.
""", encoding="utf-8")
    for r in resultados:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrencia", type=int, default=20)
    parser.add_argument("--duracion", type=int, default=30)
    parser.add_argument("--etiqueta", default="estres", help="nombre del archivo de resultados")
    args = parser.parse_args()
    main(args.concurrencia, args.duracion, args.etiqueta)
