import re

import httpx

from conftest import API, RUNTIME_DIR, login

CAMPOS_CATALOGO = {"id", "nombre", "categoria", "precio", "descripcion", "imagen", "disponible"}


def test_S01_catalogo_anonimo_solo_campos_publicos(http):
    r = http.get("/products")
    assert r.status_code == 200
    productos = r.json()
    assert len(productos) >= 10
    for p in productos:
        assert set(p) == CAMPOS_CATALOGO  # sin stock ni campos internos


def test_S01_filtros(http):
    disponibles = http.get("/products", params={"available": "true"}).json()
    assert all(p["disponible"] for p in disponibles)
    bebidas = http.get("/products", params={"category": "bebidas"}).json()
    assert bebidas and all(p["categoria"] == "bebidas" for p in bebidas)
    assert http.get("/products", params={"category": "NO VALIDA!"}).status_code == 400
    assert http.get("/products", params={"limit": 0}).status_code == 400


def test_S01_busqueda_no_interpreta_regex(http):
    r = http.get("/products", params={"q": ".*"})
    assert r.status_code == 200 and r.json() == []


def test_S02_detalle_con_personalizacion(http):
    r = http.get("/products/1")
    assert r.status_code == 200
    detalle = r.json()
    assert {"opciones", "extras"} <= set(detalle["personalizacion"])
    assert http.get("/products/9999").status_code == 404


def test_rutas_no_publicadas(http):
    assert http.get("/inexistente").status_code == 404
    assert http.delete("/products/1").status_code == 405
    # Las rutas internas de los microservicios no se publican en el gateway.
    assert http.get("/internal/orders-export").status_code == 404
    assert httpx.get("http://127.0.0.1:8000/docs").status_code == 404


def test_errores_controlados_con_request_id(http):
    r = http.get("/products/9999")
    cuerpo = r.json()
    assert set(cuerpo) == {"error", "request_id"}
    assert re.fullmatch(r"[a-f0-9]{32}", r.headers["X-Request-ID"])


def test_S03_registro_y_perfil(http, email_unico):
    r = http.post("/auth/register", json={"nombre": "Cliente Prueba", "email": email_unico,
                                          "password": "ClavePrueba123", "telefono": "+56933333333"})
    assert r.status_code == 201, r.text
    assert set(r.json()) == {"user_id", "email"}
    assert http.post("/auth/register", json={"nombre": "Otro", "email": email_unico,
                                             "password": "ClavePrueba123"}).status_code == 409
    cab = login(email_unico, "ClavePrueba123")
    perfil = http.get("/clients/me", headers=cab).json()
    assert perfil == {"user_id": r.json()["user_id"], "nombre": "Cliente Prueba", "email": email_unico,
                      "telefono": "+56933333333"}


def test_S03_politica_de_contrasena(http, email_unico):
    r = http.post("/auth/register", json={"nombre": "Débil", "email": email_unico, "password": "1234"})
    assert r.status_code == 400
    # El valor rechazado no se devuelve en el error.
    assert "1234" not in r.text


def test_S06_S07_recuperacion_de_contrasena(http, email_unico):
    http.post("/auth/register", json={"nombre": "Olvidadizo", "email": email_unico, "password": "ClaveInicial1"})
    antes = set((RUNTIME_DIR / "outbox").glob("*.eml"))
    r1 = http.post("/auth/password-reset/request", json={"email": email_unico})
    r2 = http.post("/auth/password-reset/request", json={"email": "no-existe@cliente.test"})
    assert r1.status_code == r2.status_code == 202
    assert r1.json() == r2.json()  # misma respuesta: no permite enumerar cuentas
    nuevos = set((RUNTIME_DIR / "outbox").glob("*.eml")) - antes
    correo = next(c for c in nuevos if email_unico in c.read_text(encoding="utf-8"))
    token = re.search(r"token=([\w\-]+)", correo.read_text(encoding="utf-8")).group(1)

    sesion_vieja = login(email_unico, "ClaveInicial1")
    assert http.post("/auth/password-reset/confirm", json={"token": token, "password": "ClaveNueva22"}).status_code == 200
    assert http.post("/auth/password-reset/confirm", json={"token": token, "password": "OtraClave33"}).status_code == 400
    assert http.get("/clients/me", headers=sesion_vieja).status_code == 401  # sesiones revocadas
    login(email_unico, "ClaveNueva22")


def test_S11_S14_direcciones_crud(http, email_unico):
    http.post("/auth/register", json={"nombre": "Con Direcciones", "email": email_unico, "password": "ClavePrueba123"})
    cab = login(email_unico, "ClavePrueba123")
    nueva = http.post("/clients/me/addresses", headers=cab,
                      json={"alias": "Casa", "calle": "Calle Prueba", "numero": "1", "comuna": "Ñuñoa"})
    assert nueva.status_code == 201
    dir_id = nueva.json()["id"]
    r = http.put(f"/clients/me/addresses/{dir_id}", headers=cab,
                 json={"alias": "Casa", "calle": "Calle Prueba", "numero": "2", "comuna": "Ñuñoa"})
    assert r.json()["numero"] == "2"
    assert [d["id"] for d in http.get("/clients/me/addresses", headers=cab).json()] == [dir_id]
    assert http.delete(f"/clients/me/addresses/{dir_id}", headers=cab).status_code == 204
    assert http.get("/clients/me/addresses", headers=cab).json() == []


def test_S15_cotizacion_calcula_en_servidor(http):
    r = http.post("/orders/quote", json={"items": [
        {"product_id": 1, "option_id": "grande", "extras": [{"extra_id": "palta", "qty": 2}], "qty": 2,
         "precio_unitario": 1, "total_linea": 1}]})
    assert r.status_code == 200
    linea = r.json()["items"][0]
    assert linea["precio_unitario"] == 6990 + 1500 + 2 * 800
    assert r.json()["subtotal"] == linea["precio_unitario"] * 2
    assert http.post("/orders/quote", json={"items": [{"product_id": 1, "option_id": "inventada", "qty": 1}]}).status_code == 400
