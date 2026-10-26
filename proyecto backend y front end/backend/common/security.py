import base64
import json
import secrets
import time
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from cryptography.exceptions import InvalidSignature
from fastapi import Depends, HTTPException, Request

CABECERA_SERVICIO = "X-Service-Id"
CABECERA_SECRETO = "X-Service-Secret"
CABECERA_IDENTIDAD = "X-Identity"
CABECERA_FIRMA = "X-Identity-Sig"
VIGENCIA_IDENTIDAD = 60  # segundos

ROLES_VALIDOS = {"cliente", "staff", "admin"}


def _b64e(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _b64d(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


@dataclass
class Identidad:
    user_id: str
    roles: list[str] = field(default_factory=list)

    def tiene_rol(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    @property
    def es_staff(self) -> bool:
        return self.tiene_rol("staff", "admin")


# --- Firma (solo API Gateway) -------------------------------------------------

def firmar_identidad(clave_privada_pem: str, user_id: str, roles: list[str], request_id: str) -> dict:
    clave: Ed25519PrivateKey = load_pem_private_key(clave_privada_pem.encode(), password=None)
    contexto = {"sub": user_id, "roles": roles, "exp": int(time.time()) + VIGENCIA_IDENTIDAD, "rid": request_id}
    carga = _b64e(json.dumps(contexto, separators=(",", ":")).encode())
    firma = _b64e(clave.sign(carga.encode()))
    return {CABECERA_IDENTIDAD: carga, CABECERA_FIRMA: firma}


# --- Verificación (todos los servicios) ---------------------------------------

def verificar_identidad(clave_publica_pem: str, carga: str, firma: str) -> Identidad:
    clave: Ed25519PublicKey = load_pem_public_key(clave_publica_pem.encode())
    try:
        clave.verify(_b64d(firma), carga.encode())
        contexto = json.loads(_b64d(carga))
    except (InvalidSignature, ValueError):
        raise HTTPException(401, "Identidad no verificable")
    if contexto.get("exp", 0) < time.time():
        raise HTTPException(401, "Identidad expirada")
    roles = [r for r in contexto.get("roles", []) if r in ROLES_VALIDOS]
    return Identidad(user_id=contexto["sub"], roles=roles)


def servicio_llamador(*permitidos: str):

    def dependencia(request: Request) -> str:
        servicio = request.headers.get(CABECERA_SERVICIO, "")
        secreto = request.headers.get(CABECERA_SECRETO, "")
        if servicio not in permitidos:
            raise HTTPException(403, "Componente no autorizado")
        esperado = request.app.state.secretos.opcional(f"in_{servicio}")
        if not esperado or not secrets.compare_digest(secreto, esperado):
            raise HTTPException(403, "Componente no autorizado")
        request.state.llamador = servicio
        return servicio

    return dependencia


def _identidad_desde_request(request: Request) -> Identidad | None:
    carga = request.headers.get(CABECERA_IDENTIDAD)
    firma = request.headers.get(CABECERA_FIRMA)
    if not carga or not firma:
        return None
    clave_publica = request.app.state.secretos.get("identity_public_key")
    return verificar_identidad(clave_publica, carga, firma)


def identidad_opcional(request: Request) -> Identidad | None:
    return _identidad_desde_request(request)


def requiere_identidad(*roles: str):

    def dependencia(identidad: Identidad | None = Depends(identidad_opcional)) -> Identidad:
        if identidad is None:
            raise HTTPException(401, "Autenticación requerida")
        if roles and not identidad.tiene_rol(*roles):
            raise HTTPException(403, "Permiso insuficiente")
        return identidad

    return dependencia


def cabeceras_identidad(request: Request) -> dict:
    return {k: request.headers[k] for k in (CABECERA_IDENTIDAD, CABECERA_FIRMA) if k in request.headers}
