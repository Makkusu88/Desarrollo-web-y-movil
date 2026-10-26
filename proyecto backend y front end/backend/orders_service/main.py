import hashlib
import hmac
import os
import secrets
import threading
from datetime import datetime, timedelta
from typing import Literal

from fastapi import Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from common.db import conectar
from common.security import Identidad, requiere_identidad, servicio_llamador
from common.web import ahora, crear_app, log
from orders_service.inventory_client import InventarioGrpc

SERVICIO = "orders"
TTL_PAGO = int(os.getenv("ORDER_PAYMENT_TTL_SECONDS", "600"))
COSTO_ENVIO = 1990
MAX_PENDIENTES = 3
INTERVALO_MANTENCION = 10

TRANSICIONES_STAFF = {
    ("PAGADO", "EN_PREPARACION"): None,
    ("EN_PREPARACION", "LISTO"): None,
    ("LISTO", "EN_REPARTO"): "DELIVERY",
    ("LISTO", "ENTREGADO"): "RETIRO",
    ("EN_REPARTO", "ENTREGADO"): "DELIVERY",
}
ESTADOS = ["PENDIENTE_PAGO", "PAGADO", "EN_PREPARACION", "LISTO", "EN_REPARTO", "ENTREGADO", "ANULADO"]


class ExtraIn(BaseModel):
    extra_id: str = Field(pattern=r"^[a-z0-9_]{1,30}$")
    qty: int = Field(ge=0, le=5)


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="ignore")  # precio/total enviados por el navegador se descartan
    product_id: int = Field(ge=1)
    option_id: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,30}$")
    extras: list[ExtraIn] = Field(default_factory=list, max_length=5)
    qty: int = Field(ge=1, le=10)


class CotizacionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    items: list[ItemIn] = Field(min_length=1, max_length=20)


class PedidoIn(CotizacionIn):
    tipo_entrega: Literal["RETIRO", "DELIVERY"]
    direccion_id: str | None = Field(default=None, pattern=r"^DIR-[a-f0-9]{10}$")
    notas: str | None = Field(default=None, max_length=140)


class EstadoIn(BaseModel):
    estado: Literal["EN_PREPARACION", "LISTO", "EN_REPARTO", "ENTREGADO"]


class PagoConfirmadoIn(BaseModel):
    payment_id: str = Field(pattern=r"^PAY-[A-F0-9]{10}$")


# --- Aplicación ---------------------------------------------------------------

def iniciar(app):
    db = conectar(SERVICIO, app.state.secretos)
    db.orders.create_index([("user_id", ASCENDING), ("creado_en", DESCENDING)])
    db.orders.create_index([("estado", ASCENDING), ("expira_en", ASCENDING)])
    db.orders.create_index([("actualizado_en", ASCENDING)])
    db.orders.create_index([("user_id", ASCENDING), ("idempotency_key", ASCENDING)], unique=True,
                           partialFilterExpression={"idempotency_key": {"$type": "string"}})
    app.state.db = db
    app.state.inventario = InventarioGrpc(app.state.secretos)
    app.state.detener = threading.Event()
    hilo = threading.Thread(target=mantencion, args=(app,), daemon=True)
    hilo.start()


def detener(app):
    app.state.detener.set()


app = crear_app(SERVICIO, "Orders Service", al_iniciar=iniciar, al_detener=detener)
gateway_o_graphql = Depends(servicio_llamador("gateway", "graphql"))
cliente = requiere_identidad("cliente")
staff = requiere_identidad("staff", "admin")
autenticado = requiere_identidad("cliente", "staff", "admin")


def db_de(request: Request):
    return request.app.state.db


def evento(estado: str, por: str, motivo: str | None = None) -> dict:
    return {"estado": estado, "en": ahora(), "por": por, **({"motivo": motivo} if motivo else {})}


def a_dto(doc: dict, ident: Identidad | None) -> dict:
    """DTO hacia el frontend. user_id, contacto y marcas internas no salen al
    cliente; staff ve contacto y dirección porque los necesita para despachar."""
    dto = {
        "id": doc["_id"], "estado": doc["estado"], "tipo_entrega": doc["tipo_entrega"],
        "items": doc["items"], "subtotal": doc["subtotal"], "costo_envio": doc["costo_envio"],
        "total": doc["total"], "notas": doc.get("notas"), "creado_en": doc["creado_en"],
        "actualizado_en": doc["actualizado_en"], "expira_en": doc.get("expira_en"),
        "historial": [{k: v for k, v in h.items() if k != "por"} for h in doc.get("historial", [])],
        "direccion": doc.get("direccion"), "requiere_reembolso": doc.get("requiere_reembolso", False),
    }
    if ident and ident.es_staff:
        dto["contacto"] = doc.get("contacto")
    return dto


def puede_ver(doc: dict, ident: Identidad) -> bool:
    return doc["user_id"] == ident.user_id or ident.es_staff


# --- Cotización y creación ----------------------------------------------------

def lineas_dict(cotizacion) -> list[dict]:
    return [{"product_id": l.product_id, "nombre": l.nombre, "opcion": l.opcion, "extras": list(l.extras),
             "qty": l.qty, "precio_unitario": l.unit_price, "total_linea": l.line_total} for l in cotizacion.lines]


@app.post("/quote", dependencies=[Depends(servicio_llamador("gateway"))])
def cotizar(datos: CotizacionIn, request: Request):
    """Precio oficial del carrito antes de confirmar (no reserva stock)."""
    cot = request.app.state.inventario.cotizar([i.model_dump() for i in datos.items], request.state.request_id)
    return {"items": lineas_dict(cot), "subtotal": cot.subtotal}


@app.post("/orders", status_code=201, dependencies=[Depends(servicio_llamador("gateway"))])
def crear_pedido(datos: PedidoIn, request: Request, ident: Identidad = Depends(cliente),
                 idempotency_key: str | None = Header(default=None, max_length=64)):
    db, inventario, rid = db_de(request), request.app.state.inventario, request.state.request_id

    if idempotency_key:
        previo = db.orders.find_one({"user_id": ident.user_id, "idempotency_key": idempotency_key})
        if previo:
            return a_dto(previo, ident)
    if db.orders.count_documents({"user_id": ident.user_id, "estado": "PENDIENTE_PAGO"}) >= MAX_PENDIENTES:
        raise HTTPException(409, "Tienes demasiados pedidos pendientes de pago")

    interno = request.app.state.interno
    direccion = None
    if datos.tipo_entrega == "DELIVERY":
        if not datos.direccion_id:
            raise HTTPException(400, "Debes indicar una dirección para delivery")
        resp = interno.llamar("clients", "GET", f"/internal/clients/{ident.user_id}/delivery-data/{datos.direccion_id}",
                              request=request, propagar_identidad=False)
        if resp.status_code == 404:
            raise HTTPException(404, "Dirección no encontrada")
        if resp.status_code != 200:
            raise HTTPException(503, "Servicio de clientes no disponible")
        entrega = resp.json()
        direccion, contacto = entrega["direccion"], entrega["contacto"]
    else:
        resp = interno.llamar("clients", "GET", f"/internal/clients/{ident.user_id}/contact",
                              request=request, propagar_identidad=False)
        if resp.status_code != 200:
            raise HTTPException(503, "Servicio de clientes no disponible")
        contacto = resp.json()

    cot = inventario.cotizar([i.model_dump() for i in datos.items], rid)
    lineas = lineas_dict(cot)
    costo_envio = COSTO_ENVIO if datos.tipo_entrega == "DELIVERY" else 0
    order_id = f"PED-{secrets.token_hex(4).upper()}"

    inventario.reservar(order_id, lineas, rid)  # 409 si no hay stock; nada queda guardado
    momento = ahora()
    doc = {
        "_id": order_id, "user_id": ident.user_id, "estado": "PENDIENTE_PAGO", "tipo_entrega": datos.tipo_entrega,
        "direccion": direccion, "contacto": contacto, "notas": datos.notas, "items": lineas,
        "subtotal": cot.subtotal, "costo_envio": costo_envio, "total": cot.subtotal + costo_envio,
        "creado_en": momento, "actualizado_en": momento, "expira_en": momento + timedelta(seconds=TTL_PAGO),
        "historial": [evento("PENDIENTE_PAGO", "cliente")],
    }
    if idempotency_key:
        doc["idempotency_key"] = idempotency_key
    try:
        db.orders.insert_one(doc)
    except DuplicateKeyError:
        # Doble envío simultáneo con la misma Idempotency-Key: gana el primero.
        inventario.liberar(order_id, rid)
        return a_dto(db.orders.find_one({"user_id": ident.user_id, "idempotency_key": idempotency_key}), ident)
    except Exception:
        inventario.liberar(order_id, rid)
        raise
    log(SERVICIO, "pedido_creado", request_id=rid, pedido=order_id, total=doc["total"])
    return a_dto(doc, ident)


# --- Consultas ----------------------------------------------------------------

@app.get("/orders/me", dependencies=[gateway_o_graphql])
def mis_pedidos(request: Request, ident: Identidad = Depends(autenticado),
                limit: int = Query(default=10, ge=1, le=20), offset: int = Query(default=0, ge=0)):
    db = db_de(request)
    filtro = {"user_id": ident.user_id}
    docs = db.orders.find(filtro).sort("creado_en", -1).skip(offset).limit(limit)
    return {"items": [a_dto(d, ident) for d in docs], "total": db.orders.count_documents(filtro)}


@app.get("/orders/{order_id}", dependencies=[gateway_o_graphql])
def ver_pedido(order_id: str, request: Request, ident: Identidad = Depends(autenticado)):
    doc = db_de(request).orders.find_one({"_id": order_id})
    # 404 tanto si no existe como si es ajeno: no se revela la existencia de pedidos de otros.
    if not doc or not puede_ver(doc, ident):
        raise HTTPException(404, "Pedido no encontrado")
    return a_dto(doc, ident)


@app.get("/orders", dependencies=[gateway_o_graphql])
def pedidos_local(request: Request, ident: Identidad = Depends(staff),
                  estado: str | None = Query(default=None, pattern=r"^[A-Z_]{4,20}$"),
                  limit: int = Query(default=20, ge=1, le=50), offset: int = Query(default=0, ge=0)):
    db = db_de(request)
    filtro = {"estado": estado} if estado else {"estado": {"$nin": ["ENTREGADO", "ANULADO"]}}
    docs = db.orders.find(filtro).sort("creado_en", 1).skip(offset).limit(limit)
    return {"items": [a_dto(d, ident) for d in docs], "total": db.orders.count_documents(filtro)}


# --- Cambios de estado --------------------------------------------------------

def liberar_stock(request_app, order_id: str, rid: str | None):
    try:
        request_app.state.inventario.liberar(order_id, rid)
        request_app.state.db.orders.update_one({"_id": order_id}, {"$unset": {"liberacion_pendiente": ""}})
    except HTTPException:
        # inventory no respondió: se reintenta en la mantención periódica.
        request_app.state.db.orders.update_one({"_id": order_id}, {"$set": {"liberacion_pendiente": True}})


@app.post("/orders/{order_id}/cancel", dependencies=[Depends(servicio_llamador("gateway"))])
def anular(order_id: str, request: Request, ident: Identidad = Depends(autenticado)):
    db = db_de(request)
    doc = db.orders.find_one({"_id": order_id})
    if not doc or not puede_ver(doc, ident):
        raise HTTPException(404, "Pedido no encontrado")
    es_admin = ident.tiene_rol("admin")
    if doc["user_id"] != ident.user_id and not es_admin:
        raise HTTPException(403, "Solo el cliente o un administrador pueden anular")
    permitidos = ["PENDIENTE_PAGO", "PAGADO"] if es_admin else ["PENDIENTE_PAGO"]
    if doc["estado"] not in permitidos:
        raise HTTPException(409, f"No se puede anular un pedido en estado {doc['estado']}")
    cambios = {"estado": "ANULADO", "actualizado_en": ahora()}
    if doc["estado"] == "PAGADO":
        cambios["requiere_reembolso"] = True
    res = db.orders.update_one({"_id": order_id, "estado": doc["estado"]},
                               {"$set": cambios, "$push": {"historial": evento("ANULADO", ident.roles[0])}})
    if res.modified_count == 0:
        raise HTTPException(409, "El pedido cambió de estado; vuelve a intentarlo")
    liberar_stock(request.app, order_id, request.state.request_id)
    return a_dto(db.orders.find_one({"_id": order_id}), ident)


@app.put("/orders/{order_id}/status", dependencies=[Depends(servicio_llamador("gateway"))])
def cambiar_estado(order_id: str, datos: EstadoIn, request: Request, ident: Identidad = Depends(staff)):
    db = db_de(request)
    doc = db.orders.find_one({"_id": order_id})
    if not doc:
        raise HTTPException(404, "Pedido no encontrado")
    clave = (doc["estado"], datos.estado)
    if clave not in TRANSICIONES_STAFF or TRANSICIONES_STAFF[clave] not in (None, doc["tipo_entrega"]):
        raise HTTPException(409, f"Transición no permitida: {doc['estado']} -> {datos.estado}")
    res = db.orders.update_one({"_id": order_id, "estado": doc["estado"]},
                               {"$set": {"estado": datos.estado, "actualizado_en": ahora()},
                                "$push": {"historial": evento(datos.estado, ident.roles[0])}})
    if res.modified_count == 0:
        raise HTTPException(409, "El pedido cambió de estado; vuelve a intentarlo")
    return a_dto(db.orders.find_one({"_id": order_id}), ident)


# --- Rutas internas -----------------------------------------------------------

@app.get("/internal/orders/{order_id}", dependencies=[Depends(servicio_llamador("payments"))])
def pedido_para_pago(order_id: str, request: Request):
    doc = db_de(request).orders.find_one({"_id": order_id}, {"user_id": 1, "estado": 1, "total": 1, "expira_en": 1})
    if not doc:
        raise HTTPException(404, "Pedido no encontrado")
    return {"id": doc["_id"], "user_id": doc["user_id"], "estado": doc["estado"], "total": doc["total"],
            "expira_en": doc.get("expira_en")}


@app.post("/internal/orders/{order_id}/payment-confirmed", dependencies=[Depends(servicio_llamador("payments"))])
def pago_confirmado(order_id: str, datos: PagoConfirmadoIn, request: Request):
    db = db_de(request)
    res = db.orders.update_one(
        {"_id": order_id, "estado": "PENDIENTE_PAGO"},
        {"$set": {"estado": "PAGADO", "pago_id": datos.payment_id, "pagado_en": ahora(), "actualizado_en": ahora()},
         "$push": {"historial": evento("PAGADO", "payments")}})
    doc = db.orders.find_one({"_id": order_id}, {"estado": 1, "pago_id": 1})
    if not doc:
        raise HTTPException(404, "Pedido no encontrado")
    if res.modified_count == 0 and doc.get("pago_id") != datos.payment_id:
        raise HTTPException(409, f"El pedido está {doc['estado']} y no admite este pago")
    if res.modified_count:
        try:
            request.app.state.inventario.confirmar(order_id, request.state.request_id)
        except HTTPException:
            db.orders.update_one({"_id": order_id}, {"$set": {"confirmacion_stock_pendiente": True}})
    return {"id": order_id, "estado": doc["estado"]}


@app.get("/internal/orders-export", dependencies=[Depends(servicio_llamador("analytics"))])
def exportar(request: Request, since: datetime | None = None, limit: int = Query(default=500, ge=1, le=1000)):
    clave = request.app.state.secretos.get("analytics_pseudonym_key").encode()
    filtro = {"actualizado_en": {"$gt": since}} if since else {}
    docs = db_de(request).orders.find(filtro).sort("actualizado_en", 1).limit(limit)
    salida = []
    for d in docs:
        salida.append({
            "id": d["_id"], "estado": d["estado"], "tipo_entrega": d["tipo_entrega"],
            "items": [{"product_id": i["product_id"], "nombre": i["nombre"], "qty": i["qty"],
                       "total_linea": i["total_linea"]} for i in d["items"]],
            "total": d["total"], "creado_en": d["creado_en"], "actualizado_en": d["actualizado_en"],
            "cliente_ref": hmac.new(clave, d["user_id"].encode(), hashlib.sha256).hexdigest()[:16],
        })
    return salida


# --- Mantención: expiración de pedidos impagos y reintentos -------------------

def mantencion(app):
    while not app.state.detener.wait(INTERVALO_MANTENCION):
        try:
            db = app.state.db
            for doc in db.orders.find({"estado": "PENDIENTE_PAGO", "expira_en": {"$lt": ahora()}}, {"_id": 1}):
                res = db.orders.update_one(
                    {"_id": doc["_id"], "estado": "PENDIENTE_PAGO"},
                    {"$set": {"estado": "ANULADO", "actualizado_en": ahora()},
                     "$push": {"historial": evento("ANULADO", "sistema", "Pago no recibido a tiempo")}})
                if res.modified_count:
                    log(SERVICIO, "pedido_expirado", pedido=doc["_id"])
                    liberar_stock(app, doc["_id"], None)
            for doc in db.orders.find({"liberacion_pendiente": True}, {"_id": 1}):
                liberar_stock(app, doc["_id"], None)
            for doc in db.orders.find({"confirmacion_stock_pendiente": True}, {"_id": 1}):
                try:
                    app.state.inventario.confirmar(doc["_id"])
                    db.orders.update_one({"_id": doc["_id"]}, {"$unset": {"confirmacion_stock_pendiente": ""}})
                except HTTPException:
                    pass
        except Exception as exc:  # noqa: BLE001 - el hilo no debe morir
            log(SERVICIO, "mantencion_error", tipo=type(exc).__name__)
