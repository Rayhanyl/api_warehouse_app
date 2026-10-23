"""Konstanta dan Enum status dokumen, jenis pergerakan stok, dan referensi dokumen (PRD Bagian 5 & FR-10)."""

from enum import Enum


class DocType(str, Enum):
    PO = "PO"
    GR = "GR"
    TRF = "TRF"
    OPN = "OPN"


class POStatus(str, Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class GRStatus(str, Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"


class TransferStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SHIPPED = "SHIPPED"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class OpnameStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MovementType(str, Enum):
    IN_PURCHASE = "IN_PURCHASE"
    OUT_TRANSFER = "OUT_TRANSFER"
    IN_TRANSFER = "IN_TRANSFER"
    ADJUSTMENT_PLUS = "ADJUSTMENT_PLUS"
    ADJUSTMENT_MINUS = "ADJUSTMENT_MINUS"


class ReferenceType(str, Enum):
    GOODS_RECEIPT = "GOODS_RECEIPT"
    STOCK_TRANSFER = "STOCK_TRANSFER"
    STOCK_OPNAME = "STOCK_OPNAME"


# Pemetaan wajib antara MovementType dan ReferenceType sesuai PRD 5.3 & constraint ck_stock_movements_type_ref_match
MOVEMENT_REFERENCE_MAP: dict[str, str] = {
    MovementType.IN_PURCHASE.value: ReferenceType.GOODS_RECEIPT.value,
    MovementType.OUT_TRANSFER.value: ReferenceType.STOCK_TRANSFER.value,
    MovementType.IN_TRANSFER.value: ReferenceType.STOCK_TRANSFER.value,
    MovementType.ADJUSTMENT_PLUS.value: ReferenceType.STOCK_OPNAME.value,
    MovementType.ADJUSTMENT_MINUS.value: ReferenceType.STOCK_OPNAME.value,
}

POSITIVE_MOVEMENT_TYPES: frozenset[str] = frozenset(
    {
        MovementType.IN_PURCHASE.value,
        MovementType.IN_TRANSFER.value,
        MovementType.ADJUSTMENT_PLUS.value,
    }
)

NEGATIVE_MOVEMENT_TYPES: frozenset[str] = frozenset(
    {
        MovementType.OUT_TRANSFER.value,
        MovementType.ADJUSTMENT_MINUS.value,
    }
)

ADJUSTMENT_MOVEMENT_TYPES: frozenset[str] = frozenset(
    {
        MovementType.ADJUSTMENT_PLUS.value,
        MovementType.ADJUSTMENT_MINUS.value,
    }
)

