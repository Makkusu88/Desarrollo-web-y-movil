import grpc
from fastapi import HTTPException

from common.config import GRPC_INVENTORY_ADDR
from common.web import log
from grpc_gen import inventory_pb2 as pb
from grpc_gen import inventory_pb2_grpc as pb_grpc

DEADLINE_S = 2.0

_ESTADOS_HTTP = {
    grpc.StatusCode.INVALID_ARGUMENT: 400,
    grpc.StatusCode.NOT_FOUND: 404,
    grpc.StatusCode.FAILED_PRECONDITION: 409,
    grpc.StatusCode.RESOURCE_EXHAUSTED: 409,
    grpc.StatusCode.PERMISSION_DENIED: 502,
}


class InventarioGrpc:
    def __init__(self, secretos):
        credenciales = grpc.ssl_channel_credentials(
            root_certificates=secretos.get("grpc_ca_cert").encode(),
            private_key=secretos.get("grpc_client_key").encode(),
            certificate_chain=secretos.get("grpc_client_cert").encode())
        self.canal = grpc.secure_channel(GRPC_INVENTORY_ADDR, credenciales)
        self.stub = pb_grpc.InventoryServiceStub(self.canal)

    def _llamar(self, metodo: str, mensaje, request_id: str | None):
        metadata = (("x-request-id", request_id),) if request_id else None
        try:
            return getattr(self.stub, metodo)(mensaje, timeout=DEADLINE_S, metadata=metadata)
        except grpc.RpcError as err:
            codigo = err.code()
            log("orders", "grpc_error", metodo=metodo, codigo=codigo.name, request_id=request_id)
            if codigo in _ESTADOS_HTTP:
                raise HTTPException(_ESTADOS_HTTP[codigo], err.details() if _ESTADOS_HTTP[codigo] < 500
                                    else "Error de integración con inventario")
            raise HTTPException(503, "Inventario no disponible")

    def cotizar(self, items: list[dict], request_id=None) -> pb.QuoteResponse:
        mensaje = pb.QuoteRequest(items=[
            pb.ItemSelection(product_id=i["product_id"], option_id=i.get("option_id") or "", qty=i["qty"],
                             extras=[pb.ExtraSelection(extra_id=e["extra_id"], qty=e["qty"]) for e in i["extras"]])
            for i in items])
        return self._llamar("QuoteItems", mensaje, request_id)

    def reservar(self, order_id: str, lineas, request_id=None) -> str:
        mensaje = pb.ReserveRequest(order_id=order_id,
                                    items=[pb.StockItem(product_id=l["product_id"], qty=l["qty"]) for l in lineas])
        return self._llamar("ReserveStock", mensaje, request_id).status

    def liberar(self, order_id: str, request_id=None) -> str:
        return self._llamar("ReleaseReservation", pb.ReservationRef(order_id=order_id), request_id).status

    def confirmar(self, order_id: str, request_id=None) -> str:
        return self._llamar("CommitReservation", pb.ReservationRef(order_id=order_id), request_id).status
