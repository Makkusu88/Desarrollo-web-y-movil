import hashlib
import hmac
import html
import json
import os
import secrets
import threading
import time

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from common.config import PUERTOS, url_servicio
from common.secret_provider import SecretProvider

WEBHOOK_URL = os.getenv("PROVIDER_WEBHOOK_URL", f"{url_servicio('gateway')}/api/v1/payments/webhook")
secretos = SecretProvider("provider")
app = FastAPI(title="Pasarela de pagos simulada", docs_url=None, redoc_url=None)
SESIONES: dict[str, dict] = {}
_lock = threading.Lock()


def autenticar(authorization: str = Header(default="")):
    if not secrets.compare_digest(authorization, f"Bearer {secretos.get('api_key')}"):
        raise HTTPException(401, "API key inválida")


@app.get("/health")
def health():
    return {"status": "ok", "servicio": "provider-sim"}


@app.post("/v1/checkout-sessions", status_code=201, dependencies=[Depends(autenticar)])
def crear_sesion(datos: dict):
    if not isinstance(datos.get("amount"), int) or datos["amount"] <= 0:
        raise HTTPException(400, "amount inválido")
    sid = f"cs_{secrets.token_hex(8)}"
    with _lock:
        SESIONES[sid] = {"id": sid, "amount": datos["amount"], "currency": datos.get("currency", "CLP"),
                         "reference": str(datos.get("reference", ""))[:40], "status": "open",
                         "return_url": str(datos.get("return_url", ""))[:200], "creada": time.time()}
    return {"id": sid, "checkout_url": f"http://localhost:{PUERTOS['provider']}/checkout/{sid}"}


@app.get("/v1/checkout-sessions/{sid}", dependencies=[Depends(autenticar)])
def ver_sesion(sid: str):
    s = SESIONES.get(sid)
    if not s:
        raise HTTPException(404, "Sesión inexistente")
    return {k: s[k] for k in ("id", "amount", "currency", "reference", "status")}


@app.get("/checkout/{sid}", response_class=HTMLResponse)
def pagina_pago(sid: str):
    s = SESIONES.get(sid)
    if not s:
        raise HTTPException(404, "Sesión inexistente")
    monto = f"${s['amount']:,}".replace(",", ".")
    abierta = s["status"] == "open"
    botones = (f"""<form method="post" action="/checkout/{sid}/approve"><button class="ok">Pagar {monto}</button></form>
                <form method="post" action="/checkout/{sid}/reject"><button class="no">Rechazar pago</button></form>"""
               if abierta else f"<p>Esta sesión ya fue procesada ({html.escape(s['status'])}).</p>")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PagoSimulado</title>
<style>body{{font-family:system-ui,sans-serif;background:#eef2f7;display:grid;place-items:center;min-height:100vh;margin:0}}
.caja{{background:#fff;padding:2rem;border-radius:12px;box-shadow:0 4px 20px #0002;max-width:360px;width:calc(100% - 32px)}}
h1{{font-size:1.2rem;margin:0 0 .25rem}} small{{color:#667}} .monto{{font-size:2rem;font-weight:700;margin:1rem 0}}
button{{width:100%;padding:.8rem;border:0;border-radius:8px;font-size:1rem;margin-top:.6rem;cursor:pointer}}
.ok{{background:#1a7f37;color:#fff}} .no{{background:#e5e7eb}}</style></head>
<body><main class="caja"><h1>PagoSimulado S.A.</h1><small>Entorno de pruebas · no se usan tarjetas reales</small>
<p>Comercio: Mr. Sandwich<br>Referencia: {html.escape(s['reference'])}</p>
<div class="monto">{monto} CLP</div>{botones}</main></body></html>"""


def notificar(s: dict, tipo: str):
    evento = {"id": f"evt_{secrets.token_hex(8)}", "type": tipo,
              "data": {"session_id": s["id"], "reference": s["reference"], "amount": s["amount"]}}
    s["ultimo_evento"] = evento
    enviar_webhook(evento)


def enviar_webhook(evento: dict) -> int:
    cuerpo = json.dumps(evento).encode()
    marca = int(time.time())
    firma = hmac.new(secretos.get("webhook_secret").encode(), f"{marca}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    estado = 0
    for intento in range(3):
        try:
            r = httpx.post(WEBHOOK_URL, content=cuerpo, timeout=5.0,
                           headers={"Content-Type": "application/json", "X-Provider-Signature": f"t={marca},v1={firma}"})
            estado = r.status_code
            if r.status_code < 500:
                break
        except httpx.HTTPError:
            estado = 0
        time.sleep(1 + intento)
    return estado


def resolver(sid: str, estado: str, tipo: str):
    with _lock:
        s = SESIONES.get(sid)
        if not s:
            raise HTTPException(404, "Sesión inexistente")
        if s["status"] != "open":
            return RedirectResponse(s["return_url"], status_code=303)
        s["status"] = estado
    notificar(s, tipo)
    return RedirectResponse(s["return_url"], status_code=303)


@app.post("/checkout/{sid}/approve")
def aprobar(sid: str):
    return resolver(sid, "approved", "checkout.approved")


@app.post("/checkout/{sid}/reject")
def rechazar(sid: str):
    return resolver(sid, "rejected", "checkout.rejected")


@app.post("/v1/test/sessions/{sid}/resend-webhook", dependencies=[Depends(autenticar)])
def reenviar(sid: str):
    """Solo para pruebas: reenvía el mismo evento (simula una notificación duplicada)."""
    s = SESIONES.get(sid)
    if not s or "ultimo_evento" not in s:
        raise HTTPException(404, "Sin evento para reenviar")
    return {"evento": s["ultimo_evento"]["id"], "estado_http": enviar_webhook(s["ultimo_evento"])}
