import base64
import hashlib
import hmac
import json
import time

import httpx

from conftest import API, PUERTOS, RUNTIME_DIR, USUARIOS, crear_pedido, gql, login, pagar_y_resolver

PEDIDO_RETIRO = [{"product_id": 4, "option_id": "normal", "qty": 1}]


# 1. Acceso anónimo al catálogo
def test_caso1_catalogo_anonimo(http):
    assert http.get("/products").status_code == 200


# 2. Operación protegida sin sesión válida
def test_caso2_sin_sesion(http):
    assert http.get("/orders/me").status_code == 401
    assert crear_pedido(http, {}, PEDIDO_RETIRO).status_code == 401
    falso = {"Authorization": "Bearer " + "x" * 43}
    assert http.get("/orders/me", headers=falso).status_code == 401
    assert http.post("/graphql", json={"query": "{misPedidos{total}}"}).status_code == 401


def test_caso2_logout_revoca_token(http):
    cab = login(USUARIOS["pedro"]["email"], USUARIOS["pedro"]["password"])
    assert http.get("/orders/me", headers=cab).status_code == 200
    assert http.post("/auth/logout", headers=cab).status_code == 200
    assert http.get("/orders/me", headers=cab).status_code == 401


# 3. Operación de administración desde un rol sin permiso
def test_caso3_rol_sin_permiso(http, tokens):
    producto = {"nombre": "Intruso", "categoria": "sandwich", "precio": 1000, "descripcion": "x" * 5,
                "imagen": "img/sandwich.jpg", "stock": 1}
    assert http.post("/admin/products", headers=tokens["ana"], json=producto).status_code == 403
    assert http.delete("/admin/products/1", headers=tokens["ana"]).status_code == 403
    assert http.post("/admin/products", headers=tokens["cocina"], json=producto).status_code == 403
    assert http.get("/orders", headers=tokens["ana"]).status_code == 403
    r = gql(http, tokens["ana"], "{ panelAdmin { stockBajo { id } } }")
    assert r.json()["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    assert r.json()["data"] is None


def test_caso3_csrf_cookie_sin_cabecera(http):
    r = httpx.post(f"{API}/auth/login", json={"email": USUARIOS["ana"]["email"], "password": USUARIOS["ana"]["password"]})
    cookie = r.cookies.get("ms_session")
    assert cookie and "HttpOnly" in r.headers["set-cookie"] and "SameSite=strict" in r.headers["set-cookie"]
    assert "access_token" not in r.json()  # el token no se entrega a JavaScript
    sin_cabecera = httpx.post(f"{API}/orders", cookies={"ms_session": cookie}, json={})
    assert sin_cabecera.status_code == 403


# 4. Consulta de un pedido ajeno
def test_caso4_pedido_ajeno(http, tokens):
    pedido = crear_pedido(http, tokens["ana"], PEDIDO_RETIRO).json()
    pid = pedido["id"]
    assert http.get(f"/orders/{pid}", headers=tokens["ana"]).status_code == 200
    ajeno = http.get(f"/orders/{pid}", headers=tokens["pedro"])
    assert ajeno.status_code == 404 and pid not in ajeno.text
    r = gql(http, tokens["pedro"], "query($id:ID!){resumenPedido(id:$id){id total direccionEntrega{calle}}}", {"id": pid})
    assert r.json()["data"]["resumenPedido"] is None
    assert r.json()["errors"][0]["extensions"]["code"] == "NOT_FOUND"
    assert http.get(f"/payments/order/{pid}", headers=tokens["pedro"]).status_code == 404
    assert http.post(f"/orders/{pid}/cancel", headers=tokens["pedro"]).status_code == 404
    assert http.post("/payments", headers=tokens["pedro"], json={"order_id": pid}).status_code == 404
    # El personal sí puede verlo (necesita despacharlo)
    assert http.get(f"/orders/{pid}", headers=tokens["cocina"]).status_code == 200
    http.post(f"/orders/{pid}/cancel", headers=tokens["ana"])


def test_caso4_campos_restringidos_graphql(http, tokens):
    pid = crear_pedido(http, tokens["ana"], PEDIDO_RETIRO).json()["id"]
    consulta = "query($id:ID!){resumenPedido(id:$id){id contacto{nombre telefono}}}"
    cliente = gql(http, tokens["ana"], consulta, {"id": pid}).json()
    assert cliente["data"]["resumenPedido"]["contacto"] is None  # el cliente no recibe datos de contacto
    staff = gql(http, tokens["cocina"], consulta, {"id": pid}).json()
    assert staff["data"]["resumenPedido"]["contacto"]["nombre"] == "Ana Ficticia"
    http.post(f"/orders/{pid}/cancel", headers=tokens["ana"])


def test_caso4_direccion_de_otro_cliente(http, tokens):
    pedro_dir = "DIR-b000000001"
    r = crear_pedido(http, tokens["ana"], PEDIDO_RETIRO, tipo="DELIVERY", direccion_id=pedro_dir)
    assert r.status_code == 404


# 5. Acceso directo al backend sin identidad autorizada
def test_caso5_acceso_directo_a_servicios_privados():
    for servicio, ruta in [("inventory", "/products"), ("orders", "/orders/me"), ("clients", "/me"),
                           ("payments", "/payments/order/PED-00000000"), ("analytics", "/reports/sales"),
                           ("auth", "/introspect")]:
        r = httpx.request("POST" if servicio == "auth" else "GET", f"http://127.0.0.1:{PUERTOS[servicio]}{ruta}",
                          json={"token": "x" * 30} if servicio == "auth" else None)
        assert r.status_code == 403, (servicio, r.status_code)
    falso = {"X-Service-Id": "gateway", "X-Service-Secret": "adivinado"}
    assert httpx.get(f"http://127.0.0.1:{PUERTOS['inventory']}/products", headers=falso).status_code == 403
    assert httpx.post(f"http://127.0.0.1:{PUERTOS['graphql']}/graphql", json={"query": "{__typename}"}).status_code == 403
    # Un servicio no puede llamar a rutas reservadas para otro (analytics -> payment-confirmed)
    r = httpx.post(f"http://127.0.0.1:{PUERTOS['orders']}/internal/orders/PED-00000000/payment-confirmed",
                   json={"payment_id": "PAY-0000000000"}, headers={"X-Service-Id": "analytics", "X-Service-Secret": "x"})
    assert r.status_code == 403


def test_caso5_identidad_inyectada_por_el_navegador(http, tokens):
    carga = base64.urlsafe_b64encode(json.dumps({"sub": "USR-a00000000001", "roles": ["admin"],
                                                 "exp": int(time.time()) + 60}).encode()).decode().rstrip("=")
    falsas = {"X-Identity": carga, "X-Identity-Sig": "AAAA", "X-Service-Id": "gateway"}
    assert http.get("/admin/products", headers=falsas).status_code == 401
    assert http.get("/admin/products", headers={**tokens["ana"], **falsas}).status_code == 403


# 6. Intento de confirmar un pago con datos alterados del frontend
def test_caso6_precio_alterado_se_ignora(http, tokens):
    r = crear_pedido(http, tokens["ana"], [{"product_id": 1, "option_id": "normal", "qty": 1,
                                            "precio_unitario": 1, "total_linea": 1, "total": 1}])
    assert r.status_code == 201
    assert r.json()["total"] == 6990
    http.post(f"/orders/{r.json()['id']}/cancel", headers=tokens["ana"])


def test_caso6_cliente_no_puede_marcar_pagado(http, tokens):
    pid = crear_pedido(http, tokens["ana"], PEDIDO_RETIRO).json()["id"]
    assert http.put(f"/orders/{pid}/status", headers=tokens["ana"], json={"estado": "PAGADO"}).status_code == 403
    # Ni siquiera el personal puede marcar PAGADO: solo payments, tras verificar al proveedor.
    assert http.put(f"/orders/{pid}/status", headers=tokens["cocina"], json={"estado": "PAGADO"}).status_code == 400
    assert http.get(f"/orders/{pid}", headers=tokens["ana"]).json()["estado"] == "PENDIENTE_PAGO"
    http.post(f"/orders/{pid}/cancel", headers=tokens["ana"])


def test_caso6_webhook_falsificado(http, tokens):
    pid = crear_pedido(http, tokens["ana"], PEDIDO_RETIRO).json()["id"]
    pago = http.post("/payments", headers=tokens["ana"], json={"order_id": pid}).json()
    sesion = pago["checkout_url"].rsplit("/", 1)[1]
    evento = json.dumps({"id": "evt_falso", "type": "checkout.approved",
                         "data": {"session_id": sesion, "reference": pago["payment_id"], "amount": pago["monto"]}}).encode()
    t = int(time.time())
    firma = hmac.new(b"secreto-adivinado", f"{t}.".encode() + evento, hashlib.sha256).hexdigest()
    for cabecera in ("", f"t={t},v1={firma}", f"t={t - 3600},v1={firma}"):
        r = http.post("/payments/webhook", content=evento,
                      headers={"Content-Type": "application/json", "X-Provider-Signature": cabecera})
        assert r.status_code == 401
    assert http.get(f"/orders/{pid}", headers=tokens["ana"]).json()["estado"] == "PENDIENTE_PAGO"
    http.post(f"/orders/{pid}/cancel", headers=tokens["ana"])


def test_caso6_pago_rechazado_no_confirma(http, tokens):
    pid = crear_pedido(http, tokens["ana"], PEDIDO_RETIRO).json()["id"]
    pago = pagar_y_resolver(http, tokens["ana"], pid, aprobar=False)
    assert http.get(f"/payments/order/{pid}", headers=tokens["ana"]).json()["estado"] == "RECHAZADO"
    assert http.get(f"/orders/{pid}", headers=tokens["ana"]).json()["estado"] == "PENDIENTE_PAGO"
    assert pago["monto"] == http.get(f"/orders/{pid}", headers=tokens["ana"]).json()["total"]
    http.post(f"/orders/{pid}/cancel", headers=tokens["ana"])


def test_logs_sin_secretos_ni_credenciales():
    contenido = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (RUNTIME_DIR / "logs").glob("*.log"))
    for u in USUARIOS.values():
        assert u["password"] not in contenido
    for prohibido in ("Bearer ", "sk_test_", "whsec_", "BEGIN PRIVATE KEY", "access_token", "mongo_password",
                      "Root Token", "Unseal Key"):
        assert prohibido not in contenido
