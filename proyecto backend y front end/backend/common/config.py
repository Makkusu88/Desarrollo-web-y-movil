import os
from pathlib import Path

HOST_INTERNO = "127.0.0.1"

PUERTOS = {
    "gateway": 8000,
    "auth": 8101,
    "clients": 8102,
    "inventory": 8103,
    "orders": 8104,
    "payments": 8105,
    "analytics": 8106,
    "graphql": 4000,
    "provider": 8300,
    "frontend": 8080,
    "vault": 8200,
    "mongo": 27018,
    "inventory_grpc": 50051,
}


def url_servicio(nombre: str) -> str:
    return os.getenv(f"URL_{nombre.upper()}", f"http://{HOST_INTERNO}:{PUERTOS[nombre]}")


GRPC_INVENTORY_ADDR = os.getenv("GRPC_INVENTORY_ADDR", f"localhost:{PUERTOS['inventory_grpc']}")

# Estado de ejecución (datos de Mongo, logs, bandeja de correo simulada) fuera de
# OneDrive para que nada se sincronice a la nube.
RUNTIME_DIR = Path(os.getenv("MRSANDWICH_RUNTIME", Path.home() / ".mrsandwich" / "runtime"))

FRONTEND_ORIGINS = [
    f"http://localhost:{PUERTOS['frontend']}",
    f"http://127.0.0.1:{PUERTOS['frontend']}",
]

BASES_DE_DATOS = {
    "auth": "ms_auth",
    "clients": "ms_clients",
    "inventory": "ms_inventory",
    "orders": "ms_orders",
    "payments": "ms_payments",
    "analytics": "ms_analytics",
}
