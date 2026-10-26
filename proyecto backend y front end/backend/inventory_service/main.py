import re

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from common.db import conectar
from common.security import Identidad, requiere_identidad, servicio_llamador
from common.web import ahora, crear_app
from inventory_service import grpc_server

SERVICIO = "inventory"
IMAGENES_PERMITIDAS = {"img/sandwich.jpg", "img/sliders.webp", "img/hamburguesa-papas.webp", "img/bebida.svg"}


class ProductoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    categoria: str = Field(pattern=r"^[a-z]{3,20}$")
    precio: int = Field(ge=100, le=100000)
    descripcion: str = Field(min_length=2, max_length=200)
    imagen: str = Field(max_length=60)
    disponible: bool = True
    stock: int = Field(ge=0, le=10000)
    stock_minimo: int = Field(ge=0, le=1000, default=5)


class StockIn(BaseModel):
    stock: int = Field(ge=0, le=10000)


def iniciar(app):
    db = conectar(SERVICIO, app.state.secretos)
    db.products.create_index([("categoria", 1), ("eliminado", 1)])
    db.reservations.create_index("status")
    app.state.db = db
    app.state.grpc = grpc_server.iniciar(db, app.state.secretos)


def detener(app):
    app.state.grpc.stop(grace=2)


app = crear_app(SERVICIO, "Inventory Service", al_iniciar=iniciar, al_detener=detener)
publico = Depends(servicio_llamador("gateway", "graphql"))


def db_de(request: Request):
    return request.app.state.db


def disponibilidad_publica(doc: dict) -> dict:
    stock = doc.pop("stock", 0)
    doc["disponible"] = bool(doc.get("disponible")) and stock > 0
    return doc


PROYECCION_CATALOGO = {"_id": 1, "nombre": 1, "categoria": 1, "precio": 1, "descripcion": 1, "imagen": 1,
                       "disponible": 1, "stock": 1}


def a_publico(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return disponibilidad_publica(doc)


# --- Catálogo público ---------------------------------------------------------

@app.get("/categories", dependencies=[publico])
def categorias(request: Request):
    return [{"id": c["_id"], "nombre": c["nombre"]} for c in db_de(request).categories.find().sort("orden", 1)]


@app.get("/products", dependencies=[publico])
def catalogo(request: Request,
             available: bool | None = None,
             category: str | None = Query(default=None, pattern=r"^[a-z]{3,20}$"),
             q: str | None = Query(default=None, max_length=40),
             limit: int = Query(default=50, ge=1, le=100),
             offset: int = Query(default=0, ge=0)):
    filtro: dict = {"eliminado": {"$ne": True}}
    if category:
        filtro["categoria"] = category
    if q:
        patron = re.escape(q.strip())
        filtro["$or"] = [{"nombre": {"$regex": patron, "$options": "i"}},
                         {"descripcion": {"$regex": patron, "$options": "i"}}]
    if available:
        filtro["disponible"] = True
        filtro["stock"] = {"$gt": 0}
    cursor = db_de(request).products.find(filtro, PROYECCION_CATALOGO).sort("_id", 1).skip(offset).limit(limit)
    return [a_publico(d) for d in cursor]


@app.get("/products/{producto_id}", dependencies=[publico])
def detalle(producto_id: int, request: Request):
    db = db_de(request)
    doc = db.products.find_one({"_id": producto_id, "eliminado": {"$ne": True}}, PROYECCION_CATALOGO)
    if not doc:
        raise HTTPException(404, "Producto no encontrado")
    pers = db.customization.find_one({"_id": doc["categoria"]}) or {"opciones": [], "extras": []}
    producto = a_publico(doc)
    producto["personalizacion"] = {"opciones": pers["opciones"], "extras": pers["extras"]}
    return producto


# --- Administración -----------------------------------------------------------

@app.get("/admin/products", dependencies=[Depends(servicio_llamador("gateway"))])
def admin_listar(request: Request, ident: Identidad = Depends(requiere_identidad("admin", "staff"))):
    proy = {**PROYECCION_CATALOGO, "stock_minimo": 1}
    return [{"id": d.pop("_id"), **d} for d in db_de(request).products.find({"eliminado": {"$ne": True}}, proy).sort("_id", 1)]


def validar_producto(db, datos: ProductoIn):
    if not db.categories.find_one({"_id": datos.categoria}):
        raise HTTPException(400, "Categoría inexistente")
    if datos.imagen not in IMAGENES_PERMITIDAS:
        raise HTTPException(400, "Imagen no permitida")


@app.post("/admin/products", status_code=201, dependencies=[Depends(servicio_llamador("gateway"))])
def admin_crear(datos: ProductoIn, request: Request, ident: Identidad = Depends(requiere_identidad("admin"))):
    db = db_de(request)
    validar_producto(db, datos)
    seq = db.counters.find_one_and_update({"_id": "products"}, {"$inc": {"seq": 1}}, upsert=True,
                                          return_document=ReturnDocument.AFTER)["seq"]
    db.products.insert_one({"_id": seq, **datos.model_dump(), "eliminado": False,
                            "creado_en": ahora(), "actualizado_en": ahora()})
    return {"id": seq, **datos.model_dump()}


@app.put("/admin/products/{producto_id}", dependencies=[Depends(servicio_llamador("gateway"))])
def admin_reemplazar(producto_id: int, datos: ProductoIn, request: Request,
                     ident: Identidad = Depends(requiere_identidad("admin"))):
    db = db_de(request)
    validar_producto(db, datos)
    res = db.products.update_one({"_id": producto_id, "eliminado": {"$ne": True}},
                                 {"$set": {**datos.model_dump(), "actualizado_en": ahora()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Producto no encontrado")
    return {"id": producto_id, **datos.model_dump()}


@app.put("/admin/products/{producto_id}/stock", dependencies=[Depends(servicio_llamador("gateway"))])
def admin_stock(producto_id: int, datos: StockIn, request: Request,
                ident: Identidad = Depends(requiere_identidad("admin", "staff"))):
    res = db_de(request).products.update_one({"_id": producto_id, "eliminado": {"$ne": True}},
                                             {"$set": {"stock": datos.stock, "actualizado_en": ahora()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Producto no encontrado")
    return {"id": producto_id, "stock": datos.stock}


@app.delete("/admin/products/{producto_id}", status_code=204, dependencies=[Depends(servicio_llamador("gateway"))])
def admin_eliminar(producto_id: int, request: Request, ident: Identidad = Depends(requiere_identidad("admin"))):
    # Baja lógica: los pedidos históricos guardan nombre y precio, y el registro
    # se conserva para trazabilidad.
    res = db_de(request).products.update_one({"_id": producto_id, "eliminado": {"$ne": True}},
                                             {"$set": {"eliminado": True, "disponible": False,
                                                       "actualizado_en": ahora()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Producto no encontrado")


# --- Rutas internas para el GraphQL Gateway -----------------------------------

class LoteIn(BaseModel):
    ids: list[int] = Field(max_length=100)


@app.post("/internal/products/batch", dependencies=[Depends(servicio_llamador("graphql"))])
def lote(datos: LoteIn, request: Request):
    cursor = db_de(request).products.find({"_id": {"$in": datos.ids}}, PROYECCION_CATALOGO)
    return [a_publico(d) for d in cursor]


@app.get("/internal/low-stock", dependencies=[Depends(servicio_llamador("graphql"))])
def stock_bajo(request: Request, ident: Identidad = Depends(requiere_identidad("admin", "staff"))):
    cursor = db_de(request).products.find(
        {"eliminado": {"$ne": True}, "$expr": {"$lte": ["$stock", "$stock_minimo"]}},
        {"_id": 1, "nombre": 1, "stock": 1, "stock_minimo": 1})
    return [{"id": d["_id"], "nombre": d["nombre"], "stock": d["stock"], "stock_minimo": d["stock_minimo"]}
            for d in cursor]
