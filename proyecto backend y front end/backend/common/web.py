import json
import re
import sys
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from common.config import url_servicio
from common.secret_provider import SecretProvider, SecretoNoDisponible
from common.security import CABECERA_SECRETO, CABECERA_SERVICIO, cabeceras_identidad

_RID_VALIDO = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


def log(servicio: str, evento: str, **campos):
    registro = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "servicio": servicio, "evento": evento, **campos}
    print(json.dumps(registro, ensure_ascii=False, default=str), file=sys.stdout, flush=True)


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def error_json(status: int, mensaje: str, request_id: str | None) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"codigo": status, "mensaje": mensaje}, "request_id": request_id})


class ClienteInterno:

    def __init__(self, origen: str, secretos: SecretProvider):
        self.origen = origen
        self.secretos = secretos
        self.http = httpx.Client(timeout=3.0)

    def llamar(self, destino: str, metodo: str, ruta: str, *, request: Request | None = None,
               json_body=None, params=None, timeout: float = 3.0,
               propagar_identidad: bool = True) -> httpx.Response:
        cabeceras = {
            CABECERA_SERVICIO: self.origen,
            CABECERA_SECRETO: self.secretos.get(f"out_{destino}"),
        }
        if request is not None:
            cabeceras["X-Request-ID"] = request.state.request_id
            if propagar_identidad:
                cabeceras.update(cabeceras_identidad(request))
        try:
            return self.http.request(metodo, f"{url_servicio(destino)}{ruta}", headers=cabeceras,
                                     json=json_body, params=params, timeout=timeout)
        except httpx.HTTPError:
            log(self.origen, "dependencia_no_disponible", destino=destino, ruta=ruta)
            raise HTTPException(503, f"Servicio {destino} no disponible")


def crear_app(servicio: str, titulo: str, al_iniciar=None, al_detener=None) -> FastAPI:
    secretos = SecretProvider(servicio)

    @asynccontextmanager
    async def ciclo_vida(app: FastAPI):
        app.state.secretos = secretos
        app.state.interno = ClienteInterno(servicio, secretos)
        if al_iniciar:
            al_iniciar(app)
        log(servicio, "inicio")
        yield
        if al_detener:
            al_detener(app)
        log(servicio, "detenido")

    app = FastAPI(title=titulo, lifespan=ciclo_vida, docs_url="/docs", redoc_url=None)
    app.state.secretos = secretos
    app.state.servicio = servicio

    @app.middleware("http")
    async def correlacion(request: Request, call_next):
        rid = request.headers.get("X-Request-ID", "")
        if not _RID_VALIDO.match(rid):
            rid = uuid.uuid4().hex
        request.state.request_id = rid
        inicio = time.perf_counter()
        try:
            respuesta = await call_next(request)
        except SecretoNoDisponible:
            respuesta = error_json(503, "Configuración segura no disponible", rid)
        except Exception as exc:  # noqa: BLE001 - nunca exponer la traza al cliente
            # Solo tipo y ubicación (archivo:línea); el mensaje podría contener datos.
            marco = traceback.extract_tb(exc.__traceback__)[-1]
            log(servicio, "error_no_controlado", request_id=rid, tipo=type(exc).__name__,
                ubicacion=f"{Path(marco.filename).name}:{marco.lineno}")
            respuesta = error_json(500, "Error interno", rid)
        respuesta.headers["X-Request-ID"] = rid
        log(servicio, "solicitud", request_id=rid, metodo=request.method, ruta=request.url.path,
            estado=respuesta.status_code, ms=round((time.perf_counter() - inicio) * 1000, 1),
            llamador=getattr(request.state, "llamador", None))
        return respuesta

    @app.exception_handler(StarletteHTTPException)
    async def manejar_http(request: Request, exc: StarletteHTTPException):
        return error_json(exc.status_code, str(exc.detail), getattr(request.state, "request_id", None))

    @app.exception_handler(RequestValidationError)
    async def manejar_validacion(request: Request, exc: RequestValidationError):
        # Se omite el valor recibido: podría contener contraseñas o datos personales.
        detalles = [{"campo": ".".join(str(p) for p in e["loc"][1:]), "mensaje": e["msg"]} for e in exc.errors()]
        cuerpo = {"error": {"codigo": 400, "mensaje": "Datos inválidos", "detalles": detalles},
                  "request_id": getattr(request.state, "request_id", None)}
        return JSONResponse(status_code=400, content=cuerpo)

    @app.exception_handler(SecretoNoDisponible)
    async def manejar_secretos(request: Request, exc: SecretoNoDisponible):
        return error_json(503, "Configuración segura no disponible", getattr(request.state, "request_id", None))

    @app.get("/health", tags=["sistema"])
    def health():
        return {"status": "ok", "servicio": servicio}

    return app
