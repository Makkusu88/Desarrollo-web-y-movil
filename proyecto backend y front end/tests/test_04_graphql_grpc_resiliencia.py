import sys
import time

import grpc
import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from conftest import RAIZ, ProcesoSuspendido, crear_pedido, gql, pagar_y_resolver

sys.path.insert(0, str(RAIZ / "backend"))
from grpc_gen import inventory_pb2 as pb  # noqa: E402
from grpc_gen import inventory_pb2_grpc as pb_grpc  # noqa: E402

GRPC = "localhost:50051"
RECHAZOS_TLS = (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.DEADLINE_EXCEEDED)
RESUMEN = """query($id: ID!) { resumenPedido(id: $id) {
  id estado total items { nombre cantidad producto { nombre imagen disponible } } pago { estado comprobante } } }"""


# --- GraphQL --------------------------------------------------------------------

def test_agregacion_combina_tres_subsistemas(http, tokens):
    pid = crear_pedido(http, tokens["ana"], [{"product_id": 6, "option_id": "doble", "qty": 1}]).json()["id"]
    pagar_y_resolver(http, tokens["ana"], pid)
    r = gql(http, tokens["ana"], RESUMEN, {"id": pid}).json()
    assert "errors" not in r
    resumen = r["data"]["resumenPedido"]
    assert resumen["estado"] == "PAGADO"                                   # orders
    assert resumen["items"][0]["producto"]["imagen"] == "img/sliders.webp"  # inventory
    assert resumen["pago"]["estado"] == "APROBADO"                         # payments


def test_paginacion_limitada(http, tokens):
    r = gql(http, tokens["ana"], "{ misPedidos(pagina: 1, tamano: 50) { total } }").json()
    assert r["errors"][0]["extensions"]["code"] == "BAD_USER_INPUT"
    ok = gql(http, tokens["ana"], "{ misPedidos(pagina: 1, tamano: 3) { total pagina items { id } } }").json()
    assert len(ok["data"]["misPedidos"]["items"]) <= 3


def test_limite_de_costo(http, tokens):
    campo = "misPedidos(tamano: 10) { items { id items { nombre producto { id nombre imagen } } pago { estado } } }"
    consulta = "{ " + " ".join(f"a{i}: {campo}" for i in range(6)) + " }"
    r = gql(http, tokens["ana"], consulta)
    assert r.status_code == 400
    assert r.json()["errors"][0]["extensions"]["code"] == "QUERY_TOO_COSTLY"


def test_introspeccion_y_lotes_deshabilitados(http, tokens):
    r = gql(http, tokens["ana"], "{ __schema { types { name } } }").json()
    assert "errors" in r and r.get("data") is None
    lote = http.post("/graphql", headers=tokens["ana"], json=[{"query": "{misPedidos{total}}"}] * 2)
    assert lote.status_code == 400


def test_mutaciones_no_expuestas(http, tokens):
    """Las reglas transaccionales viven en REST: el schema no define mutaciones."""
    r = gql(http, tokens["ana"], 'mutation { cancelarPedido(id: "PED-00000000") }').json()
    assert r.get("data") is None and r["errors"]


# --- gRPC -------------------------------------------------------------------------

def canal(ca: str | None, cert: str | None, clave: str | None):
    credenciales = grpc.ssl_channel_credentials(root_certificates=ca.encode() if ca else None,
                                                private_key=clave.encode() if clave else None,
                                                certificate_chain=cert.encode() if cert else None)
    return grpc.secure_channel(GRPC, credenciales)


def solicitud():
    return pb.QuoteRequest(items=[pb.ItemSelection(product_id=1, option_id="normal", qty=1)])


def test_grpc_rechaza_sin_certificado_cliente(secretos_pruebas):
    stub = pb_grpc.InventoryServiceStub(canal(secretos_pruebas["grpc_ca_cert"], None, None))
    with pytest.raises(grpc.RpcError) as err:
        stub.QuoteItems(solicitud(), timeout=2)
    # El handshake TLS falla: según el momento gRPC informa UNAVAILABLE o agota el plazo.
    assert err.value.code() in RECHAZOS_TLS


def test_grpc_rechaza_certificado_de_ca_no_confiable(secretos_pruebas):
    clave = ec.generate_private_key(ec.SECP256R1())
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "orders")])  # suplanta el CN autorizado
    import datetime
    ahora = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre).public_key(clave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(ahora)
            .not_valid_after(ahora + datetime.timedelta(hours=1)).sign(clave, hashes.SHA256()))
    pem_cert = cert.public_bytes(serialization.Encoding.PEM).decode()
    pem_clave = clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
    stub = pb_grpc.InventoryServiceStub(canal(secretos_pruebas["grpc_ca_cert"], pem_cert, pem_clave))
    with pytest.raises(grpc.RpcError) as err:
        stub.QuoteItems(solicitud(), timeout=2)
    # El handshake TLS falla: según el momento gRPC informa UNAVAILABLE o agota el plazo.
    assert err.value.code() in RECHAZOS_TLS


def test_grpc_autorizacion_por_metodo(secretos_pruebas):
    stub = pb_grpc.InventoryServiceStub(canal(secretos_pruebas["grpc_ca_cert"], secretos_pruebas["grpc_client_cert"],
                                              secretos_pruebas["grpc_client_key"]))
    for metodo, mensaje in [("QuoteItems", solicitud()),
                            ("ReserveStock", pb.ReserveRequest(order_id="PED-00000000", items=[pb.StockItem(product_id=1, qty=1)])),
                            ("ReleaseReservation", pb.ReservationRef(order_id="PED-00000000"))]:
        with pytest.raises(grpc.RpcError) as err:
            getattr(stub, metodo)(mensaje, timeout=2)
        assert err.value.code() == grpc.StatusCode.PERMISSION_DENIED


# --- Indisponibilidad de dependencias ----------------------------------------------

def test_inventory_no_responde_pedido_no_se_crea(http, tokens):
    antes = http.get("/orders/me", headers=tokens["pedro"]).json()["total"]
    with ProcesoSuspendido("inventory"):
        inicio = time.perf_counter()
        r = crear_pedido(http, tokens["pedro"], [{"product_id": 9, "option_id": "350", "qty": 1}])
        duracion = time.perf_counter() - inicio
    assert r.status_code == 503
    assert duracion < 5, "el deadline gRPC (2 s) debe cortar la espera"
    assert http.get("/orders/me", headers=tokens["pedro"]).json()["total"] == antes


def test_analytics_no_responde_error_parcial(http, tokens):
    consulta = "{ panelAdmin { ventas { totalVentas } stockBajo { nombre } } }"
    with ProcesoSuspendido("analytics"):
        r = gql(http, tokens["admin"], consulta).json()
    assert r["data"]["panelAdmin"]["ventas"] is None
    assert r["data"]["panelAdmin"]["stockBajo"] is not None  # inventory sí respondió
    assert r["errors"][0]["extensions"]["code"] == "DEPENDENCY_UNAVAILABLE"


def test_payments_no_responde_resumen_parcial(http, tokens):
    pid = crear_pedido(http, tokens["ana"], [{"product_id": 10, "option_id": "350", "qty": 1}]).json()["id"]
    with ProcesoSuspendido("payments"):
        r = gql(http, tokens["ana"], RESUMEN, {"id": pid}).json()
    assert r["data"]["resumenPedido"]["estado"] == "PENDIENTE_PAGO"
    assert r["data"]["resumenPedido"]["pago"] is None
    assert any(e["path"][-1] == "pago" for e in r["errors"])
    http.post(f"/orders/{pid}/cancel", headers=tokens["ana"])


def test_proveedor_de_pagos_no_responde(http, tokens):
    pid = crear_pedido(http, tokens["ana"], [{"product_id": 10, "option_id": "350", "qty": 1}]).json()["id"]
    with ProcesoSuspendido("provider"):
        r = http.post("/payments", headers=tokens["ana"], json={"order_id": pid})
    assert r.status_code in (503, 504)
    assert http.get(f"/orders/{pid}", headers=tokens["ana"]).json()["estado"] == "PENDIENTE_PAGO"
    http.post(f"/orders/{pid}/cancel", headers=tokens["ana"])


@pytest.mark.lento
def test_gestor_de_secretos_no_responde_usa_cache(http):
    with ProcesoSuspendido("vault"):
        time.sleep(65)  # supera el TTL de caché (60 s) para forzar una relectura fallida
        r = http.get("/products")
    assert r.status_code == 200
