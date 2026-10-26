import grpc
import warnings

from grpc_gen import inventory_pb2 as inventory__pb2

GRPC_GENERATED_VERSION = '1.84.1'
GRPC_VERSION = grpc.__version__
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    raise RuntimeError(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + ' but the generated code in inventory_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
    )


class InventoryServiceStub:

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.QuoteItems = channel.unary_unary(
                '/mrsandwich.inventory.v1.InventoryService/QuoteItems',
                request_serializer=inventory__pb2.QuoteRequest.SerializeToString,
                response_deserializer=inventory__pb2.QuoteResponse.FromString,
                _registered_method=True)
        self.ReserveStock = channel.unary_unary(
                '/mrsandwich.inventory.v1.InventoryService/ReserveStock',
                request_serializer=inventory__pb2.ReserveRequest.SerializeToString,
                response_deserializer=inventory__pb2.ReservationResponse.FromString,
                _registered_method=True)
        self.ReleaseReservation = channel.unary_unary(
                '/mrsandwich.inventory.v1.InventoryService/ReleaseReservation',
                request_serializer=inventory__pb2.ReservationRef.SerializeToString,
                response_deserializer=inventory__pb2.ReservationResponse.FromString,
                _registered_method=True)
        self.CommitReservation = channel.unary_unary(
                '/mrsandwich.inventory.v1.InventoryService/CommitReservation',
                request_serializer=inventory__pb2.ReservationRef.SerializeToString,
                response_deserializer=inventory__pb2.ReservationResponse.FromString,
                _registered_method=True)


class InventoryServiceServicer:

    def QuoteItems(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ReserveStock(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ReleaseReservation(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CommitReservation(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_InventoryServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'QuoteItems': grpc.unary_unary_rpc_method_handler(
                    servicer.QuoteItems,
                    request_deserializer=inventory__pb2.QuoteRequest.FromString,
                    response_serializer=inventory__pb2.QuoteResponse.SerializeToString,
            ),
            'ReserveStock': grpc.unary_unary_rpc_method_handler(
                    servicer.ReserveStock,
                    request_deserializer=inventory__pb2.ReserveRequest.FromString,
                    response_serializer=inventory__pb2.ReservationResponse.SerializeToString,
            ),
            'ReleaseReservation': grpc.unary_unary_rpc_method_handler(
                    servicer.ReleaseReservation,
                    request_deserializer=inventory__pb2.ReservationRef.FromString,
                    response_serializer=inventory__pb2.ReservationResponse.SerializeToString,
            ),
            'CommitReservation': grpc.unary_unary_rpc_method_handler(
                    servicer.CommitReservation,
                    request_deserializer=inventory__pb2.ReservationRef.FromString,
                    response_serializer=inventory__pb2.ReservationResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'mrsandwich.inventory.v1.InventoryService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('mrsandwich.inventory.v1.InventoryService', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class InventoryService:

    @staticmethod
    def QuoteItems(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/mrsandwich.inventory.v1.InventoryService/QuoteItems',
            inventory__pb2.QuoteRequest.SerializeToString,
            inventory__pb2.QuoteResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def ReserveStock(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/mrsandwich.inventory.v1.InventoryService/ReserveStock',
            inventory__pb2.ReserveRequest.SerializeToString,
            inventory__pb2.ReservationResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def ReleaseReservation(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/mrsandwich.inventory.v1.InventoryService/ReleaseReservation',
            inventory__pb2.ReservationRef.SerializeToString,
            inventory__pb2.ReservationResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def CommitReservation(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/mrsandwich.inventory.v1.InventoryService/CommitReservation',
            inventory__pb2.ReservationRef.SerializeToString,
            inventory__pb2.ReservationResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
