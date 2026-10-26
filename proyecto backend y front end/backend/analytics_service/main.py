import os
import threading
from datetime import date, datetime, time, timezone

from fastapi import Depends, HTTPException, Query, Request
from pymongo import UpdateOne

from common.db import conectar
from common.security import Identidad, requiere_identidad, servicio_llamador
from common.web import ahora, crear_app, log

SERVICIO = "analytics"
INTERVALO = int(os.getenv("ANALYTICS_SYNC_SECONDS", "15"))
ESTADOS_VENTA = ["PAGADO", "EN_PREPARACION", "LISTO", "EN_REPARTO", "ENTREGADO"]


def iniciar(app):
    db = conectar(SERVICIO, app.state.secretos)
    db.order_facts.create_index("creado_en")
    db.order_facts.create_index("estado")
    app.state.db = db
    app.state.detener = threading.Event()
    threading.Thread(target=ciclo_etl, args=(app,), daemon=True).start()


def detener(app):
    app.state.detener.set()


app = crear_app(SERVICIO, "Analytics Service", al_iniciar=iniciar, al_detener=detener)


def sincronizar(app) -> int:
    db = app.state.db
    estado = db.etl_state.find_one({"_id": "orders"}) or {}
    desde = estado.get("ultimo")
    total = 0
    while True:
        params = {"limit": 500}
        if desde:
            params["since"] = desde.isoformat()
        resp = app.state.interno.llamar("orders", "GET", "/internal/orders-export", params=params, timeout=10.0)
        if resp.status_code != 200:
            raise RuntimeError(f"orders respondió {resp.status_code}")
        lote = resp.json()
        if not lote:
            break
        operaciones = []
        for o in lote:
            creado = datetime.fromisoformat(o["creado_en"])
            operaciones.append(UpdateOne({"_id": o["id"]}, {"$set": {
                "estado": o["estado"], "tipo_entrega": o["tipo_entrega"], "items": o["items"], "total": o["total"],
                "creado_en": creado, "dia": creado.astimezone(timezone.utc).date().isoformat(),
                "cliente_ref": o["cliente_ref"], "sincronizado_en": ahora()}}, upsert=True))
        db.order_facts.bulk_write(operaciones)
        desde = datetime.fromisoformat(lote[-1]["actualizado_en"])
        db.etl_state.update_one({"_id": "orders"}, {"$set": {"ultimo": desde, "ejecutado_en": ahora()}}, upsert=True)
        total += len(lote)
        if len(lote) < 500:
            break
    db.etl_state.update_one({"_id": "orders"}, {"$set": {"ejecutado_en": ahora()}}, upsert=True)
    return total


def ciclo_etl(app):
    while True:
        try:
            n = sincronizar(app)
            if n:
                log(SERVICIO, "etl_sincronizado", registros=n)
        except Exception as exc:  # noqa: BLE001 - orders caído: se reintenta en el siguiente ciclo
            log(SERVICIO, "etl_error", tipo=type(exc).__name__)
        if app.state.detener.wait(INTERVALO):
            return


@app.get("/reports/sales", dependencies=[Depends(servicio_llamador("graphql"))])
def reporte_ventas(request: Request, ident: Identidad = Depends(requiere_identidad("admin")),
                   desde: date | None = None, hasta: date | None = None,
                   top: int = Query(default=5, ge=1, le=20)):
    hasta = hasta or ahora().date()
    desde = desde or hasta.replace(day=1)
    if desde > hasta or (hasta - desde).days > 366:
        raise HTTPException(400, "Rango de fechas inválido (máximo 1 año)")
    db = request.app.state.db
    rango = {"creado_en": {"$gte": datetime.combine(desde, time.min, timezone.utc),
                           "$lte": datetime.combine(hasta, time.max, timezone.utc)}}
    ventas = {**rango, "estado": {"$in": ESTADOS_VENTA}}

    resumen = next(db.order_facts.aggregate([
        {"$match": ventas},
        {"$group": {"_id": None, "total": {"$sum": "$total"}, "pedidos": {"$sum": 1},
                    "clientes": {"$addToSet": "$cliente_ref"}}},
    ]), {"total": 0, "pedidos": 0, "clientes": []})
    por_dia = db.order_facts.aggregate([
        {"$match": ventas},
        {"$group": {"_id": "$dia", "pedidos": {"$sum": 1}, "ventas": {"$sum": "$total"}}},
        {"$sort": {"_id": 1}},
    ])
    top_productos = db.order_facts.aggregate([
        {"$match": ventas}, {"$unwind": "$items"},
        {"$group": {"_id": "$items.product_id", "nombre": {"$last": "$items.nombre"},
                    "unidades": {"$sum": "$items.qty"}, "ventas": {"$sum": "$items.total_linea"}}},
        {"$sort": {"unidades": -1, "ventas": -1}}, {"$limit": top},
    ])
    por_estado = db.order_facts.aggregate([
        {"$match": rango}, {"$group": {"_id": "$estado", "cantidad": {"$sum": 1}}}, {"$sort": {"_id": 1}}])
    por_entrega = db.order_facts.aggregate([
        {"$match": ventas}, {"$group": {"_id": "$tipo_entrega", "cantidad": {"$sum": 1}}}, {"$sort": {"_id": 1}}])
    etl = db.etl_state.find_one({"_id": "orders"}) or {}

    pedidos = resumen["pedidos"]
    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "total_ventas": resumen["total"], "pedidos_pagados": pedidos,
        "ticket_promedio": round(resumen["total"] / pedidos) if pedidos else 0,
        "clientes_distintos": len(resumen["clientes"]),
        "por_dia": [{"dia": d["_id"], "pedidos": d["pedidos"], "ventas": d["ventas"]} for d in por_dia],
        "top_productos": [{"product_id": p["_id"], "nombre": p["nombre"], "unidades": p["unidades"],
                           "ventas": p["ventas"]} for p in top_productos],
        "por_estado": [{"clave": e["_id"], "cantidad": e["cantidad"]} for e in por_estado],
        "por_tipo_entrega": [{"clave": e["_id"], "cantidad": e["cantidad"]} for e in por_entrega],
        "actualizado_en": etl.get("ejecutado_en"),
    }
