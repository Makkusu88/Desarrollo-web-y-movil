import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from common.passwords import hash_clave  # noqa: E402

DATOS = json.loads((RAIZ / "scripts" / "seed_data.json").read_text(encoding="utf-8"))
BASES = ["ms_auth", "ms_clients", "ms_inventory", "ms_orders", "ms_payments", "ms_analytics"]


def ejecutar(cliente, reiniciar: bool = False) -> list[str]:
    ahora = datetime.now(timezone.utc)
    acciones = []
    if reiniciar:
        for base in BASES:
            for coleccion in cliente[base].list_collection_names():
                cliente[base][coleccion].drop()
        acciones.append("bases reiniciadas")

    inv = cliente["ms_inventory"]
    if inv.products.estimated_document_count() == 0:
        inv.categories.insert_many([{"_id": c["id"], "nombre": c["nombre"], "orden": c["orden"]} for c in DATOS["categorias"]])
        inv.products.insert_many([{
            "_id": p["id"], "nombre": p["nombre"], "categoria": p["categoria"], "precio": p["precio"],
            "descripcion": p["descripcion"], "imagen": p["imagen"], "disponible": True, "stock": p["stock"],
            "stock_minimo": 5, "eliminado": False, "creado_en": ahora, "actualizado_en": ahora,
        } for p in DATOS["productos"]])
        inv.customization.insert_many([{"_id": cat, **conf} for cat, conf in DATOS["personalizacion"].items()])
        inv.counters.update_one({"_id": "products"}, {"$set": {"seq": max(p["id"] for p in DATOS["productos"])}},
                                upsert=True)
        acciones.append(f"{len(DATOS['productos'])} productos")

    auth, clients = cliente["ms_auth"], cliente["ms_clients"]
    for u in DATOS["usuarios"]:
        if auth.credentials.find_one({"_id": u["user_id"]}):
            continue
        auth.credentials.insert_one({"_id": u["user_id"], "email": u["email"], "password_hash": hash_clave(u["password"]),
                                     "roles": u["roles"], "activo": True, "intentos_fallidos": 0,
                                     "bloqueado_hasta": None, "creado_en": ahora})
        clients.clients.update_one({"user_id": u["user_id"]}, {"$setOnInsert": {
            "user_id": u["user_id"], "nombre": u["nombre"], "email": u["email"], "telefono": u["telefono"],
            "creado_en": ahora}}, upsert=True)
        for d in u.get("direcciones", []):
            clients.addresses.update_one({"id": d["id"]}, {"$setOnInsert": {**d, "user_id": u["user_id"],
                                                                            "creado_en": ahora}}, upsert=True)
        acciones.append(f"usuario {u['roles'][0]}")
    return acciones
