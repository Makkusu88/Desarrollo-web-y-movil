from concurrent import futures

import grpc
from pymongo.errors import DuplicateKeyError

from common.config import PUERTOS
from common.web import ahora, log
from grpc_gen import inventory_pb2 as pb
from grpc_gen import inventory_pb2_grpc as pb_grpc

AUTORIZADOS = {
    "QuoteItems": {"orders"},
    "ReserveStock": {"orders"},
    "ReleaseReservation": {"orders"},
    "CommitReservation": {"orders"},
}
MAX_ITEMS = 20
MAX_CANTIDAD = 10


def _autorizar(context: grpc.ServicerContext, metodo: str):
    cn = [v.decode() for v in context.auth_context().get("x509_common_name", [])]
    if not cn or cn[0] not in AUTORIZADOS[metodo]:
        log("inventory", "grpc_denegado", metodo=metodo, cn=cn)
        context.abort(grpc.StatusCode.PERMISSION_DENIED, "Identidad de servicio no autorizada")


class InventoryServicer(pb_grpc.InventoryServiceServicer):
    def __init__(self, db):
        self.db = db

    def QuoteItems(self, request, context):
        _autorizar(context, "QuoteItems")
        if not 1 <= len(request.items) <= MAX_ITEMS:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"El pedido debe tener entre 1 y {MAX_ITEMS} líneas")
        lineas, subtotal = [], 0
        for item in request.items:
            if not 1 <= item.qty <= MAX_CANTIDAD:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Cantidad fuera de rango (1-{MAX_CANTIDAD})")
            prod = self.db.products.find_one({"_id": item.product_id, "eliminado": {"$ne": True}})
            if not prod or not prod.get("disponible"):
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Producto {item.product_id} no disponible")
            pers = self.db.customization.find_one({"_id": prod["categoria"]}) or {"opciones": [], "extras": []}
            opciones = {o["id"]: o for o in pers["opciones"]}
            opcion = opciones.get(item.option_id) if item.option_id else (pers["opciones"] or [None])[0]
            if pers["opciones"] and opcion is None:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Opción no válida para el producto")
            extras_validos = {e["id"]: e for e in pers["extras"]}
            unitario = prod["precio"] + (opcion["precio"] if opcion else 0)
            descripcion_extras = []
            vistos = set()
            for ex in item.extras:
                extra = extras_validos.get(ex.extra_id)
                if extra is None or ex.extra_id in vistos or not 0 <= ex.qty <= extra.get("max", 5):
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Extra no válido")
                vistos.add(ex.extra_id)
                if ex.qty:
                    unitario += extra["precio"] * ex.qty
                    descripcion_extras.append(f"{extra['nombre']} x{ex.qty}")
            total_linea = unitario * item.qty
            subtotal += total_linea
            lineas.append(pb.QuotedLine(product_id=prod["_id"], nombre=prod["nombre"],
                                        opcion=opcion["nombre"] if opcion else "", extras=descripcion_extras,
                                        qty=item.qty, unit_price=unitario, line_total=total_linea))
        return pb.QuoteResponse(lines=lineas, subtotal=subtotal)

    def ReserveStock(self, request, context):
        _autorizar(context, "ReserveStock")
        if not request.order_id or not 1 <= len(request.items) <= MAX_ITEMS:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Reserva inválida")
        cantidades: dict[int, int] = {}
        for it in request.items:
            cantidades[it.product_id] = cantidades.get(it.product_id, 0) + it.qty

        # 1) El documento de reserva actúa como candado de idempotencia.
        try:
            self.db.reservations.insert_one({"_id": request.order_id, "status": "PENDING",
                                             "items": [{"product_id": p, "qty": q} for p, q in cantidades.items()],
                                             "creado_en": ahora()})
        except DuplicateKeyError:
            existente = self.db.reservations.find_one({"_id": request.order_id})
            return pb.ReservationResponse(order_id=request.order_id, status=existente["status"])

        # 2) Descuento atómico por producto; si uno falla se revierten los anteriores.
        aplicados = []
        for producto_id, qty in cantidades.items():
            res = self.db.products.update_one(
                {"_id": producto_id, "eliminado": {"$ne": True}, "stock": {"$gte": qty}},
                {"$inc": {"stock": -qty}})
            if res.modified_count == 0:
                for pid, q in aplicados:
                    self.db.products.update_one({"_id": pid}, {"$inc": {"stock": q}})
                self.db.reservations.delete_one({"_id": request.order_id})
                nombre = (self.db.products.find_one({"_id": producto_id}, {"nombre": 1}) or {}).get("nombre", producto_id)
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, f"Stock insuficiente para {nombre}")
            aplicados.append((producto_id, qty))
        self.db.reservations.update_one({"_id": request.order_id}, {"$set": {"status": "ACTIVE"}})
        return pb.ReservationResponse(order_id=request.order_id, status="ACTIVE")

    def ReleaseReservation(self, request, context):
        _autorizar(context, "ReleaseReservation")
        reserva = self.db.reservations.find_one_and_update(
            {"_id": request.order_id, "status": {"$in": ["ACTIVE", "COMMITTED"]}},
            {"$set": {"status": "RELEASED", "liberada_en": ahora()}})
        if reserva:
            for it in reserva["items"]:
                self.db.products.update_one({"_id": it["product_id"]}, {"$inc": {"stock": it["qty"]}})
            return pb.ReservationResponse(order_id=request.order_id, status="RELEASED")
        existente = self.db.reservations.find_one({"_id": request.order_id})
        if not existente:
            context.abort(grpc.StatusCode.NOT_FOUND, "Reserva inexistente")
        return pb.ReservationResponse(order_id=request.order_id, status=existente["status"])

    def CommitReservation(self, request, context):
        _autorizar(context, "CommitReservation")
        self.db.reservations.update_one({"_id": request.order_id, "status": "ACTIVE"},
                                        {"$set": {"status": "COMMITTED", "confirmada_en": ahora()}})
        existente = self.db.reservations.find_one({"_id": request.order_id})
        if not existente:
            context.abort(grpc.StatusCode.NOT_FOUND, "Reserva inexistente")
        if existente["status"] != "COMMITTED":
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Reserva en estado {existente['status']}")
        return pb.ReservationResponse(order_id=request.order_id, status="COMMITTED")


def iniciar(db, secretos) -> grpc.Server:
    credenciales = grpc.ssl_server_credentials(
        [(secretos.get("grpc_server_key").encode(), secretos.get("grpc_server_cert").encode())],
        root_certificates=secretos.get("grpc_ca_cert").encode(),
        require_client_auth=True)
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=16),
                           options=[("grpc.max_receive_message_length", 64 * 1024),
                                    ("grpc.max_send_message_length", 256 * 1024)])
    pb_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(db), servidor)
    servidor.add_secure_port(f"127.0.0.1:{PUERTOS['inventory_grpc']}", credenciales)
    servidor.start()
    log("inventory", "grpc_iniciado", puerto=PUERTOS["inventory_grpc"])
    return servidor
