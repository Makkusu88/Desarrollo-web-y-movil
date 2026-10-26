import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta

import httpx
from fastapi import Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from starlette.concurrency import run_in_threadpool

from common.config import url_servicio
from common.db import conectar
from common.security import Identidad, requiere_identidad, servicio_llamador
from common.web import ahora, crear_app, log

SERVICIO = "payments"
TOLERANCIA_FIRMA_S = 300
URL_RETORNO = "http://localhost:8080/pedido.html"


class PagoIn(BaseModel):
    order_id: str = Field(pattern=r"^PED-[A-F0-9]{8}$")


def iniciar(app):
    db = conectar(SERVICIO, app.state.secretos)
    db.payments.create_index("order_id")
    db.payments.create_index("order_id", unique=True, name="un_pago_aprobado_por_pedido",
                              partialFilterExpression={"estado": "APROBADO"})
    db.processed_events.create_index("recibido_en")
    app.state.db = db
    app.state.proveedor = httpx.Client(base_url=url_servicio("provider"), timeout=5.0)


app = crear_app(SERVICIO, "Payments Service", al_iniciar=iniciar)
cliente = requiere_identidad("cliente")


def db_de(request: Request):
    return request.app.state.db


def proveedor(request: Request, metodo: str, ruta: str, **kwargs) -> httpx.Response:
    clave = request.app.state.secretos.get("provider_api_key")
    try:
        return request.app.state.proveedor.request(metodo, ruta, headers={"Authorization": f"Bearer {clave}"}, **kwargs)
    except httpx.HTTPError:
        log(SERVICIO, "proveedor_no_disponible", request_id=request.state.request_id)
        raise HTTPException(503, "Proveedor de pagos no disponible")


def a_dto(p: dict) -> dict:
    return {"payment_id": p["_id"], "order_id": p["order_id"], "estado": p["estado"], "monto": p["monto"],
            "comprobante": p.get("comprobante"), "checkout_url": p.get("checkout_url") if p["estado"] == "INICIADO" else None}


@app.post("/payments", status_code=201, dependencies=[Depends(servicio_llamador("gateway"))])
def iniciar_pago(datos: PagoIn, request: Request, ident: Identidad = Depends(cliente)):
    db = db_de(request)
    resp = request.app.state.interno.llamar("orders", "GET", f"/internal/orders/{datos.order_id}",
                                            request=request, propagar_identidad=False)
    if resp.status_code == 404:
        raise HTTPException(404, "Pedido no encontrado")
    if resp.status_code != 200:
        raise HTTPException(503, "Servicio de pedidos no disponible")
    pedido = resp.json()
    if pedido["user_id"] != ident.user_id:
        raise HTTPException(404, "Pedido no encontrado")
    if pedido["estado"] != "PENDIENTE_PAGO":
        raise HTTPException(409, f"El pedido está {pedido['estado']} y no admite un nuevo pago")

    vigente = db.payments.find_one({"order_id": datos.order_id, "estado": "INICIADO",
                                    "creado_en": {"$gt": ahora() - timedelta(minutes=10)}})
    if vigente:
        return a_dto(vigente)  # reintento del usuario: se reutiliza la misma sesión

    payment_id = f"PAY-{secrets.token_hex(5).upper()}"
    doc = {"_id": payment_id, "order_id": datos.order_id, "user_id": ident.user_id, "monto": pedido["total"],
           "estado": "INICIADO", "creado_en": ahora(), "actualizado_en": ahora()}
    db.payments.insert_one(doc)
    try:
        r = proveedor(request, "POST", "/v1/checkout-sessions", json={
            "amount": pedido["total"], "currency": "CLP", "reference": payment_id,
            "return_url": f"{URL_RETORNO}?id={datos.order_id}"})
        if r.status_code != 201:
            raise HTTPException(502, "El proveedor de pagos rechazó la solicitud")
    except HTTPException:
        # Sin sesión en el proveedor el intento no es reutilizable: el siguiente crea otro.
        db.payments.update_one({"_id": payment_id}, {"$set": {"estado": "FALLIDO", "actualizado_en": ahora()}})
        raise
    sesion = r.json()
    doc = db.payments.find_one_and_update(
        {"_id": payment_id},
        {"$set": {"sesion_proveedor": sesion["id"], "checkout_url": sesion["checkout_url"]}},
        return_document=ReturnDocument.AFTER)
    log(SERVICIO, "pago_iniciado", request_id=request.state.request_id, pago=payment_id, pedido=datos.order_id)
    return a_dto(doc)


def verificar_firma(secreto: str, cabecera: str, cuerpo: bytes) -> bool:
    try:
        partes = dict(p.split("=", 1) for p in cabecera.split(","))
        marca = int(partes["t"])
        firma = partes["v1"]
    except (ValueError, KeyError):
        return False
    if abs(time.time() - marca) > TOLERANCIA_FIRMA_S:
        return False
    esperada = hmac.new(secreto.encode(), f"{marca}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma)


def siguiente_comprobante(db) -> str:
    seq = db.counters.find_one_and_update({"_id": "comprobante"}, {"$inc": {"seq": 1}}, upsert=True,
                                          return_document=ReturnDocument.AFTER)["seq"]
    return f"CMP-{ahora():%Y}-{seq:06d}"


@app.post("/webhook", dependencies=[Depends(servicio_llamador("gateway"))])
async def webhook(request: Request, x_provider_signature: str = Header(default="")):
    cuerpo = await request.body()
    if not verificar_firma(request.app.state.secretos.get("provider_webhook_secret"), x_provider_signature, cuerpo):
        log(SERVICIO, "webhook_firma_invalida", request_id=request.state.request_id)
        raise HTTPException(401, "Firma inválida")
    try:
        evento = json.loads(cuerpo)
        evento_id, tipo, datos = evento["id"], evento["type"], evento["data"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "Evento mal formado")
    return await run_in_threadpool(procesar_evento, request, evento_id, tipo, datos)


def procesar_evento(request: Request, evento_id: str, tipo: str, datos: dict):
    db = db_de(request)
    try:
        db.processed_events.insert_one({"_id": evento_id, "estado": "PROCESANDO", "recibido_en": ahora()})
    except DuplicateKeyError:
        log(SERVICIO, "webhook_duplicado", request_id=request.state.request_id, evento_id=evento_id)
        return {"recibido": True, "duplicado": True}

    try:
        resultado = aplicar_evento(request, db, tipo, datos)
    except HTTPException:
        db.processed_events.delete_one({"_id": evento_id})  # permitir que el proveedor reintente
        raise
    db.processed_events.update_one({"_id": evento_id}, {"$set": {"estado": "PROCESADO", "resultado": resultado}})
    return {"recibido": True, "resultado": resultado}


def aplicar_evento(request: Request, db, tipo: str, datos: dict) -> str:
    pago = db.payments.find_one({"_id": datos.get("reference"), "sesion_proveedor": datos.get("session_id")})
    if not pago:
        return "ignorado_pago_desconocido"
    if pago["estado"] != "INICIADO":
        return f"ignorado_estado_{pago['estado']}"

    # Segunda verificación: el estado y el monto se consultan al proveedor.
    r = proveedor(request, "GET", f"/v1/checkout-sessions/{pago['sesion_proveedor']}")
    if r.status_code != 200:
        raise HTTPException(503, "No fue posible verificar el pago con el proveedor")
    sesion = r.json()
    if sesion["amount"] != pago["monto"] or sesion["reference"] != pago["_id"]:
        db.payments.update_one({"_id": pago["_id"]}, {"$set": {"estado": "INCONSISTENTE", "actualizado_en": ahora()}})
        log(SERVICIO, "pago_inconsistente", pago=pago["_id"])
        return "inconsistente"

    if tipo == "checkout.rejected" and sesion["status"] == "rejected":
        db.payments.update_one({"_id": pago["_id"]}, {"$set": {"estado": "RECHAZADO", "actualizado_en": ahora()}})
        return "rechazado"
    if not (tipo == "checkout.approved" and sesion["status"] == "approved"):
        return "ignorado_estado_proveedor"

    resp = request.app.state.interno.llamar(
        "orders", "POST", f"/internal/orders/{pago['order_id']}/payment-confirmed",
        request=request, propagar_identidad=False, json_body={"payment_id": pago["_id"]})
    if resp.status_code == 409:
        # El pedido expiró o fue anulado antes de que llegara el pago.
        db.payments.update_one({"_id": pago["_id"]},
                               {"$set": {"estado": "REQUIERE_REEMBOLSO", "actualizado_en": ahora()}})
        log(SERVICIO, "pago_requiere_reembolso", pago=pago["_id"], pedido=pago["order_id"])
        return "requiere_reembolso"
    if resp.status_code != 200:
        raise HTTPException(503, "Servicio de pedidos no disponible")
    db.payments.update_one({"_id": pago["_id"]},
                           {"$set": {"estado": "APROBADO", "comprobante": siguiente_comprobante(db),
                                     "actualizado_en": ahora()}})
    log(SERVICIO, "pago_aprobado", pago=pago["_id"], pedido=pago["order_id"])
    return "aprobado"


@app.get("/payments/order/{order_id}", dependencies=[Depends(servicio_llamador("gateway"))])
def pago_de_pedido(order_id: str, request: Request,
                   ident: Identidad = Depends(requiere_identidad("cliente", "staff", "admin"))):
    filtro = {"order_id": order_id}
    if not ident.es_staff:
        filtro["user_id"] = ident.user_id
    pago = db_de(request).payments.find_one(filtro, sort=[("creado_en", -1)])
    if not pago:
        raise HTTPException(404, "Sin pagos para este pedido")
    return a_dto(pago)


@app.get("/internal/payments/by-orders", dependencies=[Depends(servicio_llamador("graphql"))])
def pagos_por_pedidos(request: Request, ids: str = Query(max_length=1100),
                      ident: Identidad = Depends(requiere_identidad("cliente", "staff", "admin"))):
    lista = [i for i in ids.split(",") if i][:100]
    filtro: dict = {"order_id": {"$in": lista}}
    if not ident.es_staff:
        filtro["user_id"] = ident.user_id
    ultimo: dict[str, dict] = {}
    for p in db_de(request).payments.find(filtro).sort("creado_en", 1):
        ultimo[p["order_id"]] = p
    return [{"order_id": oid, "estado": p["estado"], "comprobante": p.get("comprobante")} for oid, p in ultimo.items()]
