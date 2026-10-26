import uuid

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from common.db import conectar
from common.security import Identidad, requiere_identidad, servicio_llamador
from common.web import ahora, crear_app

SERVICIO = "clients"
MAX_DIRECCIONES = 5


class PerfilIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    telefono: str | None = Field(default=None, pattern=r"^\+?\d{8,12}$")


class ClienteNuevoIn(PerfilIn):
    user_id: str = Field(pattern=r"^USR-[a-f0-9]{12}$")
    email: str = Field(max_length=120)


class DireccionIn(BaseModel):
    alias: str = Field(min_length=1, max_length=30)
    calle: str = Field(min_length=2, max_length=80)
    numero: str = Field(min_length=1, max_length=10)
    comuna: str = Field(min_length=2, max_length=40)
    referencia: str | None = Field(default=None, max_length=120)


CAMPOS_PERFIL = {"_id": 0, "user_id": 1, "nombre": 1, "email": 1, "telefono": 1}
CAMPOS_DIRECCION = {"_id": 0, "id": 1, "alias": 1, "calle": 1, "numero": 1, "comuna": 1, "referencia": 1}


def iniciar(app):
    db = conectar(SERVICIO, app.state.secretos)
    db.clients.create_index([("user_id", ASCENDING)], unique=True)
    db.clients.create_index([("email", ASCENDING)], unique=True)
    db.addresses.create_index([("user_id", ASCENDING), ("id", ASCENDING)], unique=True)
    app.state.db = db


app = crear_app(SERVICIO, "Clients Service", al_iniciar=iniciar)
desde_gateway = Depends(servicio_llamador("gateway"))
cliente = requiere_identidad("cliente", "staff", "admin")


def db_de(request: Request):
    return request.app.state.db


# --- Rutas para el propio cliente (vía API Gateway) ---------------------------

@app.get("/me", dependencies=[desde_gateway])
def mi_perfil(request: Request, ident: Identidad = Depends(cliente)):
    perfil = db_de(request).clients.find_one({"user_id": ident.user_id}, CAMPOS_PERFIL)
    if not perfil:
        raise HTTPException(404, "Perfil no encontrado")
    return perfil


@app.put("/me", dependencies=[desde_gateway])
def actualizar_perfil(datos: PerfilIn, request: Request, ident: Identidad = Depends(cliente)):
    perfil = db_de(request).clients.find_one_and_update(
        {"user_id": ident.user_id},
        {"$set": {"nombre": datos.nombre, "telefono": datos.telefono, "actualizado_en": ahora()}},
        projection=CAMPOS_PERFIL, return_document=ReturnDocument.AFTER)
    if not perfil:
        raise HTTPException(404, "Perfil no encontrado")
    return perfil


@app.get("/me/addresses", dependencies=[desde_gateway])
def mis_direcciones(request: Request, ident: Identidad = Depends(cliente)):
    return list(db_de(request).addresses.find({"user_id": ident.user_id}, CAMPOS_DIRECCION).sort("creado_en", 1))


@app.post("/me/addresses", status_code=201, dependencies=[desde_gateway])
def crear_direccion(datos: DireccionIn, request: Request, ident: Identidad = Depends(cliente)):
    db = db_de(request)
    if db.addresses.count_documents({"user_id": ident.user_id}) >= MAX_DIRECCIONES:
        raise HTTPException(409, f"Máximo {MAX_DIRECCIONES} direcciones por cliente")
    doc = {"id": f"DIR-{uuid.uuid4().hex[:10]}", "user_id": ident.user_id, **datos.model_dump(), "creado_en": ahora()}
    db.addresses.insert_one(doc)
    return {k: doc[k] for k in CAMPOS_DIRECCION if k in doc and k != "_id"}


@app.put("/me/addresses/{direccion_id}", dependencies=[desde_gateway])
def reemplazar_direccion(direccion_id: str, datos: DireccionIn, request: Request,
                         ident: Identidad = Depends(cliente)):
    doc = db_de(request).addresses.find_one_and_update(
        {"id": direccion_id, "user_id": ident.user_id},
        {"$set": {**datos.model_dump(), "actualizado_en": ahora()}},
        projection=CAMPOS_DIRECCION, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(404, "Dirección no encontrada")
    return doc


@app.delete("/me/addresses/{direccion_id}", status_code=204, dependencies=[desde_gateway])
def eliminar_direccion(direccion_id: str, request: Request, ident: Identidad = Depends(cliente)):
    res = db_de(request).addresses.delete_one({"id": direccion_id, "user_id": ident.user_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Dirección no encontrada")


# --- Rutas internas (solo otros microservicios) -------------------------------

@app.post("/internal/clients", status_code=201, dependencies=[Depends(servicio_llamador("auth"))])
def crear_cliente(datos: ClienteNuevoIn, request: Request):
    try:
        db_de(request).clients.insert_one({**datos.model_dump(), "email": datos.email.lower(), "creado_en": ahora()})
    except DuplicateKeyError:
        raise HTTPException(409, "Cliente ya existe")
    return {"user_id": datos.user_id}


@app.get("/internal/clients/{user_id}/delivery-data/{direccion_id}",
         dependencies=[Depends(servicio_llamador("orders"))])
def datos_entrega(user_id: str, direccion_id: str, request: Request):
    db = db_de(request)
    direccion = db.addresses.find_one({"id": direccion_id, "user_id": user_id}, CAMPOS_DIRECCION)
    perfil = db.clients.find_one({"user_id": user_id}, {"_id": 0, "nombre": 1, "telefono": 1})
    if not direccion or not perfil:
        raise HTTPException(404, "Dirección no encontrada para este cliente")
    return {"direccion": direccion, "contacto": perfil}


@app.get("/internal/clients/{user_id}/contact", dependencies=[Depends(servicio_llamador("orders"))])
def contacto(user_id: str, request: Request):
    perfil = db_de(request).clients.find_one({"user_id": user_id}, {"_id": 0, "nombre": 1, "telefono": 1})
    if not perfil:
        raise HTTPException(404, "Cliente no encontrado")
    return perfil
