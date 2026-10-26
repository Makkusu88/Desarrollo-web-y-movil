import hashlib
import json
import re
import time
import uuid
import os

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from api_gateway.routes import resolver
from common.config import FRONTEND_ORIGINS, url_servicio
from common.secret_provider import SecretProvider, SecretoNoDisponible
from common.security import CABECERA_SECRETO, CABECERA_SERVICIO, firmar_identidad
from common.web import log

SERVICIO = "gateway"
COOKIE = "ms_session"
MAX_CUERPO = 64 * 1024
TIMEOUT = httpx.Timeout(5.0, connect=2.0)
CACHE_INTROSPECCION_S = 15
LIMITES = {  # solicitudes por minuto por IP (ajustables por entorno para pruebas de carga)
    "general": int(os.getenv("RATE_GENERAL", "300")),
    "sensible": int(os.getenv("RATE_SENSIBLE", "20")),
    "graphql": int(os.getenv("RATE_GRAPHQL", "120")),
    "webhook": int(os.getenv("RATE_WEBHOOK", "120")),
}
METODOS_CON_EFECTO = {"POST", "PUT", "PATCH", "DELETE"}
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9\-]{8,64}$")

secretos = SecretProvider(SERVICIO)
app = FastAPI(title="Mr. Sandwich API Gateway", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Idempotency-Key", "X-Requested-With"],
    expose_headers=["X-Request-ID", "Retry-After"], max_age=600)


http = httpx.Client(timeout=TIMEOUT, limits=httpx.Limits(max_connections=200, max_keepalive_connections=100))
_cubetas: dict[tuple, tuple[float, float]] = {}  # (ip, politica) -> (fichas, ultimo)
_cache_tokens: dict[str, tuple[float, dict]] = {}


def error(status: int, mensaje: str, rid: str, extra_headers: dict | None = None) -> JSONResponse:
    resp = JSONResponse(status_code=status, content={"error": {"codigo": status, "mensaje": mensaje}, "request_id": rid})
    for k, v in (extra_headers or {}).items():
        resp.headers[k] = v
    return resp


def permitir(ip: str, politica: str) -> bool:
    capacidad = LIMITES[politica]
    ahora = time.monotonic()
    fichas, ultimo = _cubetas.get((ip, politica), (capacidad, ahora))
    fichas = min(capacidad, fichas + (ahora - ultimo) * capacidad / 60)
    permitido = fichas >= 1
    _cubetas[(ip, politica)] = (fichas - 1 if permitido else fichas, ahora)
    return permitido


def token_de(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(COOKIE)


def cabeceras_servicio(destino: str, rid: str) -> dict:
    return {CABECERA_SERVICIO: SERVICIO, CABECERA_SECRETO: secretos.get(f"out_{destino}"), "X-Request-ID": rid}


async def introspeccionar(token: str, rid: str) -> dict | None:
    clave = hashlib.sha256(token.encode()).hexdigest()
    en_cache = _cache_tokens.get(clave)
    if en_cache and en_cache[0] > time.monotonic():
        return en_cache[1]
    resp = await run_in_threadpool(http.post, f"{url_servicio('auth')}/introspect", json={"token": token},
                                   headers=cabeceras_servicio("auth", rid))
    if resp.status_code != 200:
        raise httpx.HTTPError(f"auth respondió {resp.status_code}")
    datos = resp.json()
    identidad = {"user_id": datos["user_id"], "roles": datos["roles"]} if datos.get("active") else None
    if identidad:
        _cache_tokens[clave] = (time.monotonic() + CACHE_INTROSPECCION_S, identidad)
    return identidad


def registrar(rid, request, estado, inicio, ruta_id=None, user=None):
    log(SERVICIO, "solicitud", request_id=rid, metodo=request.method, ruta=request.url.path, ruta_id=ruta_id,
        estado=estado, ms=round((time.perf_counter() - inicio) * 1000, 1), user_id=user,
        ip=request.client.host if request.client else None)


def con_cabeceras_seguras(resp: Response, rid: str) -> Response:
    resp.headers["X-Request-ID"] = rid
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/health")
async def health():
    return {"status": "ok", "servicio": SERVICIO}


@app.get("/api/v1/session")
async def sesion(request: Request):
    rid = uuid.uuid4().hex
    token = token_de(request)
    try:
        identidad = await introspeccionar(token, rid) if token else None
    except (httpx.HTTPError, SecretoNoDisponible):
        return con_cabeceras_seguras(error(503, "Servicio de autenticación no disponible", rid), rid)
    cuerpo = {"autenticado": bool(identidad), **(identidad or {})}
    return con_cabeceras_seguras(JSONResponse(cuerpo), rid)


@app.api_route("/api/{resto:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(resto: str, request: Request):
    rid = uuid.uuid4().hex
    inicio = time.perf_counter()
    ip = request.client.host if request.client else "desconocida"
    ruta, params = resolver(request.method, request.url.path)

    if ruta is None:
        registrar(rid, request, 404, inicio)
        return con_cabeceras_seguras(error(404, "Ruta no encontrada", rid), rid)
    if ruta == "405":
        registrar(rid, request, 405, inicio)
        return con_cabeceras_seguras(error(405, "Método no permitido", rid), rid)
    if not permitir(ip, ruta.limite):
        registrar(rid, request, 429, inicio, ruta.id)
        return con_cabeceras_seguras(error(429, "Demasiadas solicitudes", rid, {"Retry-After": "60"}), rid)

    cuerpo = await request.body()
    if len(cuerpo) > MAX_CUERPO:
        return con_cabeceras_seguras(error(413, "Solicitud demasiado grande", rid), rid)

    token = token_de(request)
    usa_cookie = token is not None and not request.headers.get("authorization")
    if (usa_cookie and request.method in METODOS_CON_EFECTO and ruta.id != "S24"
            and request.headers.get("x-requested-with") != "mrsandwich"):
        return con_cabeceras_seguras(error(403, "Solicitud sin cabecera anti-CSRF", rid), rid)

    try:
        identidad = None
        if "anon" not in ruta.acceso:
            if not token:
                registrar(rid, request, 401, inicio, ruta.id)
                return con_cabeceras_seguras(error(401, "Autenticación requerida", rid), rid)
            identidad = await introspeccionar(token, rid)
            if identidad is None:
                registrar(rid, request, 401, inicio, ruta.id)
                resp = error(401, "Sesión inválida o expirada", rid)
                resp.delete_cookie(COOKIE, path="/api")
                return con_cabeceras_seguras(resp, rid)
            if not set(identidad["roles"]) & set(ruta.acceso):
                registrar(rid, request, 403, inicio, ruta.id, identidad["user_id"])
                return con_cabeceras_seguras(error(403, "Permiso insuficiente para esta operación", rid), rid)

        # Solo se reenvía lo necesario; las cabeceras del navegador se descartan.
        cabeceras = cabeceras_servicio(ruta.destino, rid)
        if request.headers.get("content-type"):
            cabeceras["Content-Type"] = request.headers["content-type"]
        clave_idem = request.headers.get("idempotency-key")
        if clave_idem and IDEMPOTENCY_RE.match(clave_idem):
            cabeceras["Idempotency-Key"] = clave_idem
        if ruta.id == "S24" and request.headers.get("x-provider-signature"):
            cabeceras["X-Provider-Signature"] = request.headers["x-provider-signature"][:200]
        if identidad:
            cabeceras.update(firmar_identidad(secretos.get("identity_signing_key"),
                                              identidad["user_id"], identidad["roles"], rid))

        if ruta.id == "S05":  # logout: el token viaja al auth service en el cuerpo, no en la URL
            cuerpo = json.dumps({"token": token}).encode()
            cabeceras["Content-Type"] = "application/json"
            _cache_tokens.pop(hashlib.sha256(token.encode()).hexdigest(), None)

        destino = f"{url_servicio(ruta.destino)}{ruta.destino_para(params)}"
        upstream = await run_in_threadpool(http.request, request.method, destino, content=cuerpo or None,
                                           params=request.query_params if request.method == "GET" else None,
                                           headers=cabeceras)
    except SecretoNoDisponible:
        registrar(rid, request, 503, inicio, ruta.id)
        return con_cabeceras_seguras(error(503, "Configuración segura no disponible", rid), rid)
    except httpx.TimeoutException:
        registrar(rid, request, 504, inicio, ruta.id)
        return con_cabeceras_seguras(error(504, "El servicio tardó demasiado en responder", rid), rid)
    except httpx.HTTPError:
        registrar(rid, request, 503, inicio, ruta.id)
        return con_cabeceras_seguras(error(503, "Servicio no disponible", rid), rid)

    resp = Response(content=upstream.content, status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type"))

    if ruta.id == "S04" and upstream.status_code == 200:
        datos = upstream.json()
        resp = JSONResponse({"user_id": datos["user_id"], "roles": datos["roles"], "expires_in": datos["expires_in"],
                             **({"access_token": datos["access_token"]}
                                if request.headers.get("x-token-delivery") == "body" else {})})
        resp.set_cookie(COOKIE, datos["access_token"], max_age=datos["expires_in"], httponly=True,
                        samesite="strict", path="/api", secure=request.url.scheme == "https")
    if ruta.id == "S05":
        resp.delete_cookie(COOKIE, path="/api")

    registrar(rid, request, upstream.status_code, inicio, ruta.id, identidad["user_id"] if identidad else None)
    return con_cabeceras_seguras(resp, rid)
