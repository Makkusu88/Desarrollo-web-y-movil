import uuid

import httpx

from conftest import PUERTOS, crear_pedido, esperar, gql, pagar_y_resolver, stock_de


def test_flujo_completo_delivery(http, tokens):
    antes = stock_de(http, tokens["admin"], 2)
    r = crear_pedido(http, tokens["ana"], [{"product_id": 2, "option_id": "normal",
                                            "extras": [{"extra_id": "queso", "qty": 1}], "qty": 2}],
                     tipo="DELIVERY", direccion_id="DIR-a000000001")
    assert r.status_code == 201, r.text
    pedido = r.json()
    assert pedido["total"] == (5490 + 700) * 2 + 1990
    assert pedido["direccion"]["calle"] == "Calle Falsa"
    assert stock_de(http, tokens["admin"], 2) == antes - 2  # reservado al crear

    pagar_y_resolver(http, tokens["ana"], pedido["id"])
    assert http.get(f"/orders/{pedido['id']}", headers=tokens["ana"]).json()["estado"] == "PAGADO"
    pago = http.get(f"/payments/order/{pedido['id']}", headers=tokens["ana"]).json()
    assert pago["estado"] == "APROBADO" and pago["comprobante"].startswith("CMP-")

    for estado in ("EN_PREPARACION", "LISTO", "EN_REPARTO", "ENTREGADO"):
        r = http.put(f"/orders/{pedido['id']}/status", headers=tokens["cocina"], json={"estado": estado})
        assert r.status_code == 200, r.text
    final = http.get(f"/orders/{pedido['id']}", headers=tokens["ana"]).json()
    assert [h["estado"] for h in final["historial"]] == [
        "PENDIENTE_PAGO", "PAGADO", "EN_PREPARACION", "LISTO", "EN_REPARTO", "ENTREGADO"]


def test_pago_duplicado_y_notificacion_repetida(http, tokens, secretos_pruebas):
    pid = crear_pedido(http, tokens["pedro"], [{"product_id": 9, "option_id": "350", "qty": 1}]).json()["id"]
    pago = pagar_y_resolver(http, tokens["pedro"], pid)
    comprobante = http.get(f"/payments/order/{pid}", headers=tokens["pedro"]).json()["comprobante"]

    # El proveedor reenvía el mismo evento: se reconoce como duplicado y no cambia nada.
    r = httpx.post(f"http://127.0.0.1:{PUERTOS['provider']}/v1/test/sessions/{pago['sesion']}/resend-webhook",
                   headers={"Authorization": f"Bearer {secretos_pruebas['provider_api_key']}"})
    assert r.json()["estado_http"] == 200
    assert http.get(f"/payments/order/{pid}", headers=tokens["pedro"]).json()["comprobante"] == comprobante

    # Un segundo pago para un pedido ya pagado se rechaza.
    assert http.post("/payments", headers=tokens["pedro"], json={"order_id": pid}).status_code == 409


def test_reintento_de_pago_reutiliza_sesion(http, tokens):
    pid = crear_pedido(http, tokens["pedro"], [{"product_id": 10, "option_id": "350", "qty": 1}]).json()["id"]
    p1 = http.post("/payments", headers=tokens["pedro"], json={"order_id": pid}).json()
    p2 = http.post("/payments", headers=tokens["pedro"], json={"order_id": pid}).json()
    assert p1["payment_id"] == p2["payment_id"] and p1["checkout_url"] == p2["checkout_url"]
    http.post(f"/orders/{pid}/cancel", headers=tokens["pedro"])


def test_stock_insuficiente_no_crea_pedido(http, tokens):
    antes = stock_de(http, tokens["admin"], 5)
    r = crear_pedido(http, tokens["ana"], [{"product_id": 5, "option_id": "normal", "qty": antes + 1}])
    assert r.status_code in (400, 409)
    assert stock_de(http, tokens["admin"], 5) == antes


def test_reserva_atomica_entre_productos(http, tokens):
    """Si un producto del pedido no tiene stock, no se descuenta ninguno."""
    antes_1 = stock_de(http, tokens["admin"], 1)
    antes_5 = stock_de(http, tokens["admin"], 5)
    r = crear_pedido(http, tokens["ana"], [{"product_id": 1, "option_id": "normal", "qty": 1},
                                           {"product_id": 5, "option_id": "normal", "qty": min(10, antes_5 + 1)}])
    if antes_5 + 1 <= 10:
        assert r.status_code == 409
        assert stock_de(http, tokens["admin"], 1) == antes_1


def test_anulacion_recupera_stock(http, tokens):
    antes = stock_de(http, tokens["admin"], 3)
    pid = crear_pedido(http, tokens["ana"], [{"product_id": 3, "option_id": "normal", "qty": 2}]).json()["id"]
    assert stock_de(http, tokens["admin"], 3) == antes - 2
    r = http.post(f"/orders/{pid}/cancel", headers=tokens["ana"])
    assert r.json()["estado"] == "ANULADO"
    assert stock_de(http, tokens["admin"], 3) == antes
    assert http.get(f"/orders/{pid}", headers=tokens["ana"]).status_code == 200  # se conserva el historial
    assert http.post(f"/orders/{pid}/cancel", headers=tokens["ana"]).status_code == 409


def test_expiracion_libera_stock(http, tokens):
    antes = stock_de(http, tokens["admin"], 4)
    pedido = crear_pedido(http, tokens["pedro"], [{"product_id": 4, "option_id": "normal", "qty": 1}]).json()
    from datetime import datetime
    ttl = (datetime.fromisoformat(pedido["expira_en"]) - datetime.fromisoformat(pedido["creado_en"])).total_seconds()
    if ttl > 60:
        import pytest
        pytest.skip("Inicia el sistema con --ttl-pago 30 para probar la expiración")
    estado = esperar(lambda: (p := http.get(f"/orders/{pedido['id']}", headers=tokens["pedro"]).json())["estado"] == "ANULADO" and p,
                     segundos=ttl + 30)
    assert estado, "el pedido no expiró"
    assert estado["historial"][-1]["motivo"] == "Pago no recibido a tiempo"
    assert stock_de(http, tokens["admin"], 4) == antes
    # Un pago que llega después de la expiración no revive el pedido.
    assert http.post("/payments", headers=tokens["pedro"], json={"order_id": pedido["id"]}).status_code == 409


def test_idempotency_key_evita_pedidos_duplicados(http, tokens):
    clave = str(uuid.uuid4())
    items = [{"product_id": 9, "option_id": "350", "qty": 1}]
    a = crear_pedido(http, tokens["ana"], items, clave=clave).json()
    b = crear_pedido(http, tokens["ana"], items, clave=clave).json()
    assert a["id"] == b["id"]
    http.post(f"/orders/{a['id']}/cancel", headers=tokens["ana"])


def test_transiciones_invalidas(http, tokens):
    pid = crear_pedido(http, tokens["ana"], [{"product_id": 9, "option_id": "350", "qty": 1}]).json()["id"]
    assert http.put(f"/orders/{pid}/status", headers=tokens["cocina"], json={"estado": "LISTO"}).status_code == 409
    pagar_y_resolver(http, tokens["ana"], pid)
    assert http.put(f"/orders/{pid}/status", headers=tokens["cocina"], json={"estado": "EN_REPARTO"}).status_code == 409
    assert http.post(f"/orders/{pid}/cancel", headers=tokens["ana"]).status_code == 409  # cliente no anula pagado
    r = http.post(f"/orders/{pid}/cancel", headers=tokens["admin"])  # admin sí: queda para reembolso
    assert r.status_code == 200 and r.json()["requiere_reembolso"] is True


def test_baja_logica_de_producto_conserva_historial(http, tokens):
    nuevo = http.post("/admin/products", headers=tokens["admin"], json={
        "nombre": "Especial temporada", "categoria": "sandwich", "precio": 7990,
        "descripcion": "Producto de prueba", "imagen": "img/sandwich.jpg", "stock": 5}).json()
    pid = crear_pedido(http, tokens["ana"], [{"product_id": nuevo["id"], "option_id": "normal", "qty": 1}]).json()["id"]
    assert http.delete(f"/admin/products/{nuevo['id']}", headers=tokens["admin"]).status_code == 204
    assert http.get(f"/products/{nuevo['id']}").status_code == 404
    r = gql(http, tokens["ana"], "query($id:ID!){resumenPedido(id:$id){items{nombre producto{nombre disponible}}}}", {"id": pid})
    item = r.json()["data"]["resumenPedido"]["items"][0]
    assert item["nombre"] == "Especial temporada" and item["producto"]["disponible"] is False
    http.post(f"/orders/{pid}/cancel", headers=tokens["ana"])


def test_analitica_refleja_ventas(http, tokens):
    pid = crear_pedido(http, tokens["ana"], [{"product_id": 7, "option_id": "coca", "qty": 1}]).json()["id"]
    pagar_y_resolver(http, tokens["ana"], pid)
    consulta = "{ panelAdmin { ventas { pedidosPagados totalVentas topProductos { nombre unidades } } stockBajo { nombre } } }"
    previo = gql(http, tokens["admin"], consulta).json()["data"]["panelAdmin"]["ventas"]["pedidosPagados"]

    def incluido():
        datos = gql(http, tokens["admin"], consulta).json()["data"]["panelAdmin"]
        nombres = [t["nombre"] for t in datos["ventas"]["topProductos"]]
        return datos if "Combo italiano" in nombres else None

    datos = esperar(incluido, segundos=40, intervalo=2)
    assert datos, "la analítica no reflejó la venta dentro del retraso aceptado"
    assert datos["ventas"]["pedidosPagados"] >= previo
