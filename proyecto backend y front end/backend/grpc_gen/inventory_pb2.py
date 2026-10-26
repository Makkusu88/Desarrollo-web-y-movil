from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    7,
    35,
    1,
    '',
    'inventory.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0finventory.proto\x12\x17mrsandwich.inventory.v1\"/\n\x0e\x45xtraSelection\x12\x10\n\x08\x65xtra_id\x18\x01 \x01(\t\x12\x0b\n\x03qty\x18\x02 \x01(\x05\"|\n\rItemSelection\x12\x12\n\nproduct_id\x18\x01 \x01(\x05\x12\x11\n\toption_id\x18\x02 \x01(\t\x12\x37\n\x06\x65xtras\x18\x03 \x03(\x0b\x32\'.mrsandwich.inventory.v1.ExtraSelection\x12\x0b\n\x03qty\x18\x04 \x01(\x05\"E\n\x0cQuoteRequest\x12\x35\n\x05items\x18\x01 \x03(\x0b\x32&.mrsandwich.inventory.v1.ItemSelection\"\x85\x01\n\nQuotedLine\x12\x12\n\nproduct_id\x18\x01 \x01(\x05\x12\x0e\n\x06nombre\x18\x02 \x01(\t\x12\x0e\n\x06opcion\x18\x03 \x01(\t\x12\x0e\n\x06\x65xtras\x18\x04 \x03(\t\x12\x0b\n\x03qty\x18\x05 \x01(\x05\x12\x12\n\nunit_price\x18\x06 \x01(\x03\x12\x12\n\nline_total\x18\x07 \x01(\x03\"U\n\rQuoteResponse\x12\x32\n\x05lines\x18\x01 \x03(\x0b\x32#.mrsandwich.inventory.v1.QuotedLine\x12\x10\n\x08subtotal\x18\x02 \x01(\x03\",\n\tStockItem\x12\x12\n\nproduct_id\x18\x01 \x01(\x05\x12\x0b\n\x03qty\x18\x02 \x01(\x05\"U\n\x0eReserveRequest\x12\x10\n\x08order_id\x18\x01 \x01(\t\x12\x31\n\x05items\x18\x02 \x03(\x0b\x32\".mrsandwich.inventory.v1.StockItem\"\"\n\x0eReservationRef\x12\x10\n\x08order_id\x18\x01 \x01(\t\"7\n\x13ReservationResponse\x12\x10\n\x08order_id\x18\x01 \x01(\t\x12\x0e\n\x06status\x18\x02 \x01(\t2\xaf\x03\n\x10InventoryService\x12[\n\nQuoteItems\x12%.mrsandwich.inventory.v1.QuoteRequest\x1a&.mrsandwich.inventory.v1.QuoteResponse\x12\x65\n\x0cReserveStock\x12\'.mrsandwich.inventory.v1.ReserveRequest\x1a,.mrsandwich.inventory.v1.ReservationResponse\x12k\n\x12ReleaseReservation\x12\'.mrsandwich.inventory.v1.ReservationRef\x1a,.mrsandwich.inventory.v1.ReservationResponse\x12j\n\x11\x43ommitReservation\x12\'.mrsandwich.inventory.v1.ReservationRef\x1a,.mrsandwich.inventory.v1.ReservationResponseb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'inventory_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_EXTRASELECTION']._serialized_start=44
  _globals['_EXTRASELECTION']._serialized_end=91
  _globals['_ITEMSELECTION']._serialized_start=93
  _globals['_ITEMSELECTION']._serialized_end=217
  _globals['_QUOTEREQUEST']._serialized_start=219
  _globals['_QUOTEREQUEST']._serialized_end=288
  _globals['_QUOTEDLINE']._serialized_start=291
  _globals['_QUOTEDLINE']._serialized_end=424
  _globals['_QUOTERESPONSE']._serialized_start=426
  _globals['_QUOTERESPONSE']._serialized_end=511
  _globals['_STOCKITEM']._serialized_start=513
  _globals['_STOCKITEM']._serialized_end=557
  _globals['_RESERVEREQUEST']._serialized_start=559
  _globals['_RESERVEREQUEST']._serialized_end=644
  _globals['_RESERVATIONREF']._serialized_start=646
  _globals['_RESERVATIONREF']._serialized_end=680
  _globals['_RESERVATIONRESPONSE']._serialized_start=682
  _globals['_RESERVATIONRESPONSE']._serialized_end=737
  _globals['_INVENTORYSERVICE']._serialized_start=740
  _globals['_INVENTORYSERVICE']._serialized_end=1171
# @@protoc_insertion_point(module_scope)
