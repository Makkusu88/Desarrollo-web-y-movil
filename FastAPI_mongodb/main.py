from typing import List, Optional, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from contextlib import asynccontextmanager


MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "MrSandwich"

COLL_USUARIOS = "usuarios"
COLL_CATEGORIAS = "categorias"
COLL_PRODUCTOS = "productos"
COLL_INGREDIENTES = "ingredientes"
COLL_PROVEEDORES = "proveedors"

client: AsyncIOMotorClient | None = None
db = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    yield
    client.close()


app = FastAPI(title="FastAPI MrSandwich", version="1.0.0", lifespan=lifespan)


class UsuarioIn(BaseModel):
    nombre: str = Field(min_length=1, description="Nombre de usuario")
    pass_: str = Field(min_length=1, alias="pass", description="Clave")

class UsuarioOut(BaseModel):
    id: str
    nombre: str


class CategoriaIn(BaseModel):
    nombre: str = Field(min_length=1, description="Nombre de la categoria")
    descripcion: Optional[str] = None
    activo: bool = True

class CategoriaOut(CategoriaIn):
    id: str


class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1, description="Nombre de Producto")
    descripcion: Optional[str] = None
    precio: float = Field(gt=0, description="Precio > 0")
    categoria: str = Field(description="id de la categoria")
    disponible: bool = True
    imagen: Optional[str] = None

class ProductoOut(ProductoIn):
    id: str


class IngredienteIn(BaseModel):
    nombre: str = Field(min_length=1, description="Nombre del ingrediente")
    stock: float = Field(default=0, ge=0)
    unidadMedida: Optional[Literal["UNIDAD", "GRAMO", "KILOGRAMO", "MILILITRO", "LITRO"]] = None
    stockMinimo: float = Field(default=0, ge=0)

class IngredienteOut(IngredienteIn):
    id: str


class ProveedorIn(BaseModel):
    nombre: str = Field(min_length=1, description="Nombre del proveedor")
    telefono: Optional[str] = None
    correo: Optional[str] = None
    direccion: Optional[str] = None
    activo: bool = True

class ProveedorOut(ProveedorIn):
    id: str


def doc_to_usuarioout(doc) -> UsuarioOut:
    return UsuarioOut(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
    )

def doc_to_categoriaout(doc) -> CategoriaOut:
    return CategoriaOut(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        descripcion=doc.get("descripcion"),
        activo=doc.get("activo", True),
    )

def doc_to_productoout(doc) -> ProductoOut:
    return ProductoOut(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        descripcion=doc.get("descripcion"),
        precio=doc["precio"],
        categoria=str(doc.get("categoria", "")),
        disponible=doc.get("disponible", True),
        imagen=doc.get("imagen"),
    )

def doc_to_ingredienteout(doc) -> IngredienteOut:
    return IngredienteOut(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        stock=doc.get("stock", 0),
        unidadMedida=doc.get("unidadMedida"),
        stockMinimo=doc.get("stockMinimo", 0),
    )

def doc_to_proveedorout(doc) -> ProveedorOut:
    return ProveedorOut(
        id=str(doc["_id"]),
        nombre=doc["nombre"],
        telefono=doc.get("telefono"),
        correo=doc.get("correo"),
        direccion=doc.get("direccion"),
        activo=doc.get("activo", True),
    )


def validar_id(id: str) -> ObjectId:
    if not ObjectId.is_valid(id):
        raise HTTPException(400, "id invalido")
    return ObjectId(id)

def filtro_nombre(q: Optional[str]) -> dict:
    query = {}
    if q:
        query["nombre"] = {"$regex": q, "$options": "i"}
    return query


# EndPoints

@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok"}


@app.get("/usuarios", response_model=List[UsuarioOut], tags=["usuarios"])
async def listar_usuarios(
    q: Optional[str] = Query(None, description="Filtro por nombre que contenga 'q'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    cursor = db[COLL_USUARIOS].find(filtro_nombre(q)).skip(skip).limit(limit)
    usuarios: list[UsuarioOut] = []
    async for doc in cursor:
        usuarios.append(doc_to_usuarioout(doc))
    return usuarios

@app.post("/usuarios", response_model=UsuarioOut, status_code=201, tags=["usuarios"])
async def crear_usuario(usuario: UsuarioIn):
    res = await db[COLL_USUARIOS].insert_one(usuario.model_dump(by_alias=True))
    doc = await db[COLL_USUARIOS].find_one({"_id": res.inserted_id})
    return doc_to_usuarioout(doc)

@app.get("/usuarios/{usuario_id}", response_model=UsuarioOut, tags=["usuarios"])
async def obtener_usuario(usuario_id: str):
    doc = await db[COLL_USUARIOS].find_one({"_id": validar_id(usuario_id)})
    if not doc:
        raise HTTPException(404, "Usuario no encontrado")
    return doc_to_usuarioout(doc)

@app.put("/usuarios/{usuario_id}", response_model=UsuarioOut, tags=["usuarios"])
async def actualizar_usuario(usuario_id: str, usuario: UsuarioIn):
    oid = validar_id(usuario_id)
    res = await db[COLL_USUARIOS].update_one(
        {"_id": oid},
        {"$set": usuario.model_dump(by_alias=True)}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Usuario no encontrado")
    doc = await db[COLL_USUARIOS].find_one({"_id": oid})
    return doc_to_usuarioout(doc)

@app.delete("/usuarios/{usuario_id}", status_code=204, tags=["usuarios"])
async def eliminar_usuario(usuario_id: str):
    res = await db[COLL_USUARIOS].delete_one({"_id": validar_id(usuario_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Usuario no encontrado")
    return None


@app.get("/categorias", response_model=List[CategoriaOut], tags=["categorias"])
async def listar_categorias(
    q: Optional[str] = Query(None, description="Filtro por nombre que contenga 'q'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    cursor = db[COLL_CATEGORIAS].find(filtro_nombre(q)).skip(skip).limit(limit)
    categorias: list[CategoriaOut] = []
    async for doc in cursor:
        categorias.append(doc_to_categoriaout(doc))
    return categorias

@app.post("/categorias", response_model=CategoriaOut, status_code=201, tags=["categorias"])
async def crear_categoria(categoria: CategoriaIn):
    res = await db[COLL_CATEGORIAS].insert_one(categoria.model_dump())
    doc = await db[COLL_CATEGORIAS].find_one({"_id": res.inserted_id})
    return doc_to_categoriaout(doc)

@app.get("/categorias/{categoria_id}", response_model=CategoriaOut, tags=["categorias"])
async def obtener_categoria(categoria_id: str):
    doc = await db[COLL_CATEGORIAS].find_one({"_id": validar_id(categoria_id)})
    if not doc:
        raise HTTPException(404, "Categoria no encontrada")
    return doc_to_categoriaout(doc)

@app.put("/categorias/{categoria_id}", response_model=CategoriaOut, tags=["categorias"])
async def actualizar_categoria(categoria_id: str, categoria: CategoriaIn):
    oid = validar_id(categoria_id)
    res = await db[COLL_CATEGORIAS].update_one(
        {"_id": oid},
        {"$set": categoria.model_dump()}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Categoria no encontrada")
    doc = await db[COLL_CATEGORIAS].find_one({"_id": oid})
    return doc_to_categoriaout(doc)

@app.delete("/categorias/{categoria_id}", status_code=204, tags=["categorias"])
async def eliminar_categoria(categoria_id: str):
    res = await db[COLL_CATEGORIAS].delete_one({"_id": validar_id(categoria_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Categoria no encontrada")
    return None


async def producto_a_documento(producto: ProductoIn) -> dict:
    categoria_oid = validar_id(producto.categoria)
    if not await db[COLL_CATEGORIAS].find_one({"_id": categoria_oid}):
        raise HTTPException(400, "La categoria no existe")
    datos = producto.model_dump()
    datos["categoria"] = categoria_oid
    return datos

@app.get("/productos", response_model=List[ProductoOut], tags=["productos"])
async def listar_productos(
    q: Optional[str] = Query(None, description="Filtro por nombre que contenga 'q'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    cursor = db[COLL_PRODUCTOS].find(filtro_nombre(q)).skip(skip).limit(limit)
    productos: list[ProductoOut] = []
    async for doc in cursor:
        productos.append(doc_to_productoout(doc))
    return productos

@app.post("/productos", response_model=ProductoOut, status_code=201, tags=["productos"])
async def crear_producto(producto: ProductoIn):
    res = await db[COLL_PRODUCTOS].insert_one(await producto_a_documento(producto))
    doc = await db[COLL_PRODUCTOS].find_one({"_id": res.inserted_id})
    return doc_to_productoout(doc)

@app.get("/productos/{producto_id}", response_model=ProductoOut, tags=["productos"])
async def obtener_producto(producto_id: str):
    doc = await db[COLL_PRODUCTOS].find_one({"_id": validar_id(producto_id)})
    if not doc:
        raise HTTPException(404, "Producto no encontrado")
    return doc_to_productoout(doc)

@app.put("/productos/{producto_id}", response_model=ProductoOut, tags=["productos"])
async def actualizar_producto(producto_id: str, producto: ProductoIn):
    oid = validar_id(producto_id)
    res = await db[COLL_PRODUCTOS].update_one(
        {"_id": oid},
        {"$set": await producto_a_documento(producto)}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Producto no encontrado")
    doc = await db[COLL_PRODUCTOS].find_one({"_id": oid})
    return doc_to_productoout(doc)

@app.delete("/productos/{producto_id}", status_code=204, tags=["productos"])
async def eliminar_producto(producto_id: str):
    res = await db[COLL_PRODUCTOS].delete_one({"_id": validar_id(producto_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Producto no encontrado")
    return None


@app.get("/ingredientes", response_model=List[IngredienteOut], tags=["ingredientes"])
async def listar_ingredientes(
    q: Optional[str] = Query(None, description="Filtro por nombre que contenga 'q'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    cursor = db[COLL_INGREDIENTES].find(filtro_nombre(q)).skip(skip).limit(limit)
    ingredientes: list[IngredienteOut] = []
    async for doc in cursor:
        ingredientes.append(doc_to_ingredienteout(doc))
    return ingredientes

@app.post("/ingredientes", response_model=IngredienteOut, status_code=201, tags=["ingredientes"])
async def crear_ingrediente(ingrediente: IngredienteIn):
    res = await db[COLL_INGREDIENTES].insert_one(ingrediente.model_dump())
    doc = await db[COLL_INGREDIENTES].find_one({"_id": res.inserted_id})
    return doc_to_ingredienteout(doc)

@app.get("/ingredientes/{ingrediente_id}", response_model=IngredienteOut, tags=["ingredientes"])
async def obtener_ingrediente(ingrediente_id: str):
    doc = await db[COLL_INGREDIENTES].find_one({"_id": validar_id(ingrediente_id)})
    if not doc:
        raise HTTPException(404, "Ingrediente no encontrado")
    return doc_to_ingredienteout(doc)

@app.put("/ingredientes/{ingrediente_id}", response_model=IngredienteOut, tags=["ingredientes"])
async def actualizar_ingrediente(ingrediente_id: str, ingrediente: IngredienteIn):
    oid = validar_id(ingrediente_id)
    res = await db[COLL_INGREDIENTES].update_one(
        {"_id": oid},
        {"$set": ingrediente.model_dump()}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Ingrediente no encontrado")
    doc = await db[COLL_INGREDIENTES].find_one({"_id": oid})
    return doc_to_ingredienteout(doc)

@app.delete("/ingredientes/{ingrediente_id}", status_code=204, tags=["ingredientes"])
async def eliminar_ingrediente(ingrediente_id: str):
    res = await db[COLL_INGREDIENTES].delete_one({"_id": validar_id(ingrediente_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Ingrediente no encontrado")
    return None


@app.get("/proveedores", response_model=List[ProveedorOut], tags=["proveedores"])
async def listar_proveedores(
    q: Optional[str] = Query(None, description="Filtro por nombre que contenga 'q'"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    cursor = db[COLL_PROVEEDORES].find(filtro_nombre(q)).skip(skip).limit(limit)
    proveedores: list[ProveedorOut] = []
    async for doc in cursor:
        proveedores.append(doc_to_proveedorout(doc))
    return proveedores

@app.post("/proveedores", response_model=ProveedorOut, status_code=201, tags=["proveedores"])
async def crear_proveedor(proveedor: ProveedorIn):
    res = await db[COLL_PROVEEDORES].insert_one(proveedor.model_dump())
    doc = await db[COLL_PROVEEDORES].find_one({"_id": res.inserted_id})
    return doc_to_proveedorout(doc)

@app.get("/proveedores/{proveedor_id}", response_model=ProveedorOut, tags=["proveedores"])
async def obtener_proveedor(proveedor_id: str):
    doc = await db[COLL_PROVEEDORES].find_one({"_id": validar_id(proveedor_id)})
    if not doc:
        raise HTTPException(404, "Proveedor no encontrado")
    return doc_to_proveedorout(doc)

@app.put("/proveedores/{proveedor_id}", response_model=ProveedorOut, tags=["proveedores"])
async def actualizar_proveedor(proveedor_id: str, proveedor: ProveedorIn):
    oid = validar_id(proveedor_id)
    res = await db[COLL_PROVEEDORES].update_one(
        {"_id": oid},
        {"$set": proveedor.model_dump()}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Proveedor no encontrado")
    doc = await db[COLL_PROVEEDORES].find_one({"_id": oid})
    return doc_to_proveedorout(doc)

@app.delete("/proveedores/{proveedor_id}", status_code=204, tags=["proveedores"])
async def eliminar_proveedor(proveedor_id: str):
    res = await db[COLL_PROVEEDORES].delete_one({"_id": validar_id(proveedor_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Proveedor no encontrado")
    return None
