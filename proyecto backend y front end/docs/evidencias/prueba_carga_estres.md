# Prueba de carga (estres) — resultados medidos

Entorno: Windows-11-10.0.26200-SP0 · 12 núcleos lógicos · 31.7 GB RAM ·
Python 3.12.3 · 2026-10-28T16:57:00. Todos los componentes en el mismo PC (el generador de carga compite
por CPU con el backend, por lo que los valores son conservadores).

Tipo: **medición (no proyección)**. Comando: `python scripts/prueba_carga.py --concurrencia 20 --duracion 30 --etiqueta estres`
con el sistema iniciado con `python run_all.py --reset --perfil carga`.

| Escenario | Concurrencia | Solicitudes | Throughput (req/s) | p50 ms | p95 ms | p99 ms | Errores | CPU backend % prom/máx | Memoria backend máx MB | Objetivo p95 ms | Resultado |
|---|---|---|---|---|---|---|---|---|---|---|---|
| E1 catálogo | 20 | 28012 | 934.6 | 19.2 | 33.1 | 43.8 | 0.00% | 217.2 / 250.6 | 890.3 | 200 | Cumple |
| E2 cotización (gRPC) | 20 | 21790 | 726.6 | 25.2 | 40.7 | 51.3 | 0.00% | 349.2 / 387.5 | 896.6 | 300 | Cumple |
| E3 agregación GraphQL | 20 | 18023 | 601.2 | 29.7 | 49.8 | 69.6 | 0.00% | 301.2 / 351.6 | 1038.2 | 500 | Cumple |

CPU: suma de los procesos del backend (100 % = un núcleo completo). Memoria: RSS sumada de esos procesos.
