from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ExtraSelection(_message.Message):
    __slots__ = ("extra_id", "qty")
    EXTRA_ID_FIELD_NUMBER: _ClassVar[int]
    QTY_FIELD_NUMBER: _ClassVar[int]
    extra_id: str
    qty: int
    def __init__(self, extra_id: _Optional[str] = ..., qty: _Optional[int] = ...) -> None: ...

class ItemSelection(_message.Message):
    __slots__ = ("product_id", "option_id", "extras", "qty")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    OPTION_ID_FIELD_NUMBER: _ClassVar[int]
    EXTRAS_FIELD_NUMBER: _ClassVar[int]
    QTY_FIELD_NUMBER: _ClassVar[int]
    product_id: int
    option_id: str
    extras: _containers.RepeatedCompositeFieldContainer[ExtraSelection]
    qty: int
    def __init__(self, product_id: _Optional[int] = ..., option_id: _Optional[str] = ..., extras: _Optional[_Iterable[_Union[ExtraSelection, _Mapping]]] = ..., qty: _Optional[int] = ...) -> None: ...

class QuoteRequest(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[ItemSelection]
    def __init__(self, items: _Optional[_Iterable[_Union[ItemSelection, _Mapping]]] = ...) -> None: ...

class QuotedLine(_message.Message):
    __slots__ = ("product_id", "nombre", "opcion", "extras", "qty", "unit_price", "line_total")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    NOMBRE_FIELD_NUMBER: _ClassVar[int]
    OPCION_FIELD_NUMBER: _ClassVar[int]
    EXTRAS_FIELD_NUMBER: _ClassVar[int]
    QTY_FIELD_NUMBER: _ClassVar[int]
    UNIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    LINE_TOTAL_FIELD_NUMBER: _ClassVar[int]
    product_id: int
    nombre: str
    opcion: str
    extras: _containers.RepeatedScalarFieldContainer[str]
    qty: int
    unit_price: int
    line_total: int
    def __init__(self, product_id: _Optional[int] = ..., nombre: _Optional[str] = ..., opcion: _Optional[str] = ..., extras: _Optional[_Iterable[str]] = ..., qty: _Optional[int] = ..., unit_price: _Optional[int] = ..., line_total: _Optional[int] = ...) -> None: ...

class QuoteResponse(_message.Message):
    __slots__ = ("lines", "subtotal")
    LINES_FIELD_NUMBER: _ClassVar[int]
    SUBTOTAL_FIELD_NUMBER: _ClassVar[int]
    lines: _containers.RepeatedCompositeFieldContainer[QuotedLine]
    subtotal: int
    def __init__(self, lines: _Optional[_Iterable[_Union[QuotedLine, _Mapping]]] = ..., subtotal: _Optional[int] = ...) -> None: ...

class StockItem(_message.Message):
    __slots__ = ("product_id", "qty")
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    QTY_FIELD_NUMBER: _ClassVar[int]
    product_id: int
    qty: int
    def __init__(self, product_id: _Optional[int] = ..., qty: _Optional[int] = ...) -> None: ...

class ReserveRequest(_message.Message):
    __slots__ = ("order_id", "items")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    items: _containers.RepeatedCompositeFieldContainer[StockItem]
    def __init__(self, order_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[StockItem, _Mapping]]] = ...) -> None: ...

class ReservationRef(_message.Message):
    __slots__ = ("order_id",)
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    def __init__(self, order_id: _Optional[str] = ...) -> None: ...

class ReservationResponse(_message.Message):
    __slots__ = ("order_id", "status")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    status: str
    def __init__(self, order_id: _Optional[str] = ..., status: _Optional[str] = ...) -> None: ...
