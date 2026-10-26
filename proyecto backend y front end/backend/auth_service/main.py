import hashlib
import os
import re
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from common.config import RUNTIME_DIR
from common.db import conectar
from common.passwords import hash_clave, verificar_clave
from common.security import servicio_llamador
from common.web import ahora, crear_app, log

SERVICIO = "auth"
VIGENCIA_SESION_MIN = int(os.getenv("SESSION_TTL_MINUTES", "30"))
VIGENCIA_RESET_MIN = 15
MAX_INTENTOS = 5
BLOQUEO_MIN = 5
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
OUTBOX = RUNTIME_DIR / "outbox"
URL_RESTABLECER = "http://localhost:8080/restablecer.html"


# --- Contraseñas -------------------------------------------------------------

HASH_FICTICIO = hash_clave(secrets.token_urlsafe(16))  # iguala tiempos si el email no existe


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def validar_politica_clave(clave: str) -> str:
    if len(clave) < 8 or not re.search(r"[A-Za-z]", clave) or not re.search(r"\d", clave):
        raise ValueError("La contraseña debe tener al menos 8 caracteres, con letras y números")
    return clave


# --- Modelos ------------------------------------------------------------------

class RegistroIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    email: str = Field(max_length=120)
    password: str = Field(max_length=128)
    telefono: str | None = Field(default=None, pattern=r"^\+?\d{8,12}$")

    @field_validator("email")
    @classmethod
    def email_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Email no válido")
        return v

    @field_validator("password")
    @classmethod
    def clave_valida(cls, v: str) -> str:
        return validar_politica_clave(v)


class LoginIn(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(max_length=128)


class TokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResetSolicitudIn(BaseModel):
    email: str = Field(max_length=120)


class ResetConfirmIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(max_length=128)

    @field_validator("password")
    @classmethod
    def clave_valida(cls, v: str) -> str:
        return validar_politica_clave(v)


# --- Aplicación ---------------------------------------------------------------

def iniciar(app):
    db = conectar(SERVICIO, app.state.secretos)
    db.credentials.create_index([("email", ASCENDING)], unique=True)
    db.sessions.create_index("expires_at", expireAfterSeconds=0)
    db.sessions.create_index("user_id")
    db.reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    app.state.db = db
    OUTBOX.mkdir(parents=True, exist_ok=True)


app = crear_app(SERVICIO, "Auth Service", al_iniciar=iniciar)
solo_gateway = Depends(servicio_llamador("gateway"))


def db_de(request: Request):
    return request.app.state.db


@app.post("/register", status_code=201, dependencies=[solo_gateway])
def registrar(datos: RegistroIn, request: Request):
    db = db_de(request)
    user_id = f"USR-{uuid.uuid4().hex[:12]}"
    try:
        db.credentials.insert_one({
            "_id": user_id, "email": datos.email, "password_hash": hash_clave(datos.password),
            "roles": ["cliente"], "activo": True, "intentos_fallidos": 0, "bloqueado_hasta": None,
            "creado_en": ahora(),
        })
    except DuplicateKeyError:
        raise HTTPException(409, "El email ya está registrado")

    # El perfil (nombre, teléfono, direcciones) pertenece al sistema clients.
    resp = request.app.state.interno.llamar(
        "clients", "POST", "/internal/clients", request=request, propagar_identidad=False,
        json_body={"user_id": user_id, "nombre": datos.nombre, "email": datos.email, "telefono": datos.telefono})
    if resp.status_code != 201:
        db.credentials.delete_one({"_id": user_id})  # compensación: no dejar cuentas sin perfil
        raise HTTPException(503, "No fue posible completar el registro")
    return {"user_id": user_id, "email": datos.email}


@app.post("/login", dependencies=[solo_gateway])
def login(datos: LoginIn, request: Request):
    db = db_de(request)
    cred = db.credentials.find_one({"email": datos.email.strip().lower()})
    if cred and cred.get("bloqueado_hasta") and cred["bloqueado_hasta"] > ahora():
        raise HTTPException(429, "Cuenta bloqueada temporalmente por intentos fallidos")

    valido = verificar_clave(datos.password, cred["password_hash"] if cred else HASH_FICTICIO)
    if not cred or not valido or not cred.get("activo", True):
        if cred:
            intentos = cred.get("intentos_fallidos", 0) + 1
            cambios = {"intentos_fallidos": intentos}
            if intentos >= MAX_INTENTOS:
                cambios = {"intentos_fallidos": 0, "bloqueado_hasta": ahora() + timedelta(minutes=BLOQUEO_MIN)}
                log(SERVICIO, "cuenta_bloqueada", request_id=request.state.request_id, user_id=cred["_id"])
            db.credentials.update_one({"_id": cred["_id"]}, {"$set": cambios})
        raise HTTPException(401, "Credenciales inválidas")

    db.credentials.update_one({"_id": cred["_id"]}, {"$set": {"intentos_fallidos": 0, "bloqueado_hasta": None}})
    token = secrets.token_urlsafe(32)
    db.sessions.insert_one({
        "_id": sha256(token), "user_id": cred["_id"], "roles": cred["roles"],
        "creado_en": ahora(), "expires_at": ahora() + timedelta(minutes=VIGENCIA_SESION_MIN),
    })
    log(SERVICIO, "login_exitoso", request_id=request.state.request_id, user_id=cred["_id"])
    return {"access_token": token, "token_type": "bearer", "expires_in": VIGENCIA_SESION_MIN * 60,
            "user_id": cred["_id"], "roles": cred["roles"]}


@app.post("/introspect", dependencies=[solo_gateway])
def introspect(datos: TokenIn, request: Request):
    sesion = db_de(request).sessions.find_one({"_id": sha256(datos.token)})
    if not sesion or sesion["expires_at"] <= ahora():
        return {"active": False}
    return {"active": True, "user_id": sesion["user_id"], "roles": sesion["roles"],
            "expires_at": sesion["expires_at"].isoformat()}


@app.post("/logout", dependencies=[solo_gateway])
def logout(datos: TokenIn, request: Request):
    db_de(request).sessions.delete_one({"_id": sha256(datos.token)})
    return {"mensaje": "Sesión finalizada"}


@app.post("/password-reset/request", status_code=202, dependencies=[solo_gateway])
def solicitar_reset(datos: ResetSolicitudIn, request: Request):
    db = db_de(request)
    cred = db.credentials.find_one({"email": datos.email.strip().lower()})
    if cred:
        token = secrets.token_urlsafe(32)
        db.reset_tokens.insert_one({"_id": sha256(token), "user_id": cred["_id"], "usado": False,
                                    "expires_at": ahora() + timedelta(minutes=VIGENCIA_RESET_MIN)})
        enviar_correo(cred["email"], "Recupera tu contraseña de Mr. Sandwich",
                      f"Para definir una nueva contraseña abre: {URL_RESTABLECER}?token={token}\n"
                      f"El enlace vence en {VIGENCIA_RESET_MIN} minutos.")
    # Misma respuesta exista o no el email: evita enumerar cuentas.
    return {"mensaje": "Si el email está registrado, recibirás un enlace de recuperación"}


@app.post("/password-reset/confirm", dependencies=[solo_gateway])
def confirmar_reset(datos: ResetConfirmIn, request: Request):
    db = db_de(request)
    registro = db.reset_tokens.find_one_and_update(
        {"_id": sha256(datos.token), "usado": False, "expires_at": {"$gt": ahora()}},
        {"$set": {"usado": True}})
    if not registro:
        raise HTTPException(400, "Enlace inválido o vencido")
    db.credentials.update_one({"_id": registro["user_id"]},
                              {"$set": {"password_hash": hash_clave(datos.password), "intentos_fallidos": 0,
                                        "bloqueado_hasta": None}})
    db.sessions.delete_many({"user_id": registro["user_id"]})  # revoca sesiones abiertas
    return {"mensaje": "Contraseña actualizada"}


def enviar_correo(destinatario: str, asunto: str, cuerpo: str):
    nombre = f"{ahora().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.eml"
    Path(OUTBOX / nombre).write_text(
        f"To: {destinatario}\nFrom: no-responder@mrsandwich.test\nSubject: {asunto}\n\n{cuerpo}\n", encoding="utf-8")
