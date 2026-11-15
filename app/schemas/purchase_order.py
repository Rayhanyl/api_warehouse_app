"""Schema Pydantic untuk Purchase Order (PO) dan PO Lines (FR-04, PRD 5.1, 6.9, Tahap 36)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validation import (
    pydantic_optional_str,
    pydantic_required_str,
    pydantic_validate_decimal_qty,
)
from app.schemas.common import DecimalStr


class POLineInput(BaseModel):
    item_id: int = Field(..., gt=0)
    qty_ordered: Decimal
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("qty_ordered", mode="before")
    @classmethod
    def _validate_qty_ordered(cls, v: Any) -> Decimal:
        return pydantic_validate_decimal_qty(v, label="Jumlah pesan", allow_zero=False)

    @field_validator("notes")
    @classmethod
    def _val_notes(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)


class POLineOut(BaseModel):
    id: int
    po_id: int
    item_id: int
    item_sku: str
    item_barcode: str | None = None
    item_name: str
    uom_id: int
    uom_code: str
    allow_decimal: bool
    qty_ordered: DecimalStr
    qty_received: DecimalStr
    qty_closed: DecimalStr = Decimal("0.0000")
    qty_remaining: DecimalStr = Decimal("0.0000")
    line_status: str = "OPEN"
    line_closed_reason: str | None = None
    line_closed_at: datetime | None = None
    line_closed_by: int | None = None
    notes: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class PurchaseOrderCreate(BaseModel):
    supplier_id: int = Field(..., gt=0)
    warehouse_id: int = Field(..., gt=0)
    order_date: date
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    lines: list[POLineInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_delivery_date(self) -> "PurchaseOrderCreate":
        if (
            self.expected_delivery_date is not None
            and self.expected_delivery_date < self.order_date
        ):
            raise ValueError(
                "Estimasi tanggal pengiriman tidak boleh lebih awal dari tanggal pesanan."
            )
        return self


class PurchaseOrderUpdate(BaseModel):
    supplier_id: int | None = Field(default=None, gt=0)
    warehouse_id: int | None = Field(default=None, gt=0)
    order_date: date | None = None
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    lines: list[POLineInput] | None = None

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "PurchaseOrderUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        if (
            self.order_date is not None
            and self.expected_delivery_date is not None
            and self.expected_delivery_date < self.order_date
        ):
            raise ValueError(
                "Estimasi tanggal pengiriman tidak boleh lebih awal dari tanggal pesanan."
            )
        return self


class PurchaseOrderCloseRequest(BaseModel):
    closed_reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("closed_reason")
    @classmethod
    def _val_closed_reason(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Alasan penutupan PO")


class PurchaseOrderSummaryOut(BaseModel):
    id: int
    po_number: str
    supplier_id: int
    supplier_code: str
    supplier_name: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    status: str
    order_date: date
    expected_delivery_date: date | None = None
    is_overdue: bool = False
    days_overdue: int = 0
    revised_from_po_id: int | None = None
    revised_from_po_number: str | None = None
    notes: str | None = None
    line_count: int = 0
    issued_at: datetime | None = None
    issued_by: int | None = None
    closed_reason: str | None = None
    closed_at: datetime | None = None
    closed_by: int | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class PurchaseOrderOut(PurchaseOrderSummaryOut):
    supplier_phone: str | None = None
    supplier_fax: str | None = None
    supplier_email: str | None = None
    supplier_address: str | None = None
    supplier_npwp: str | None = None
    supplier_bank_name: str | None = None
    supplier_bank_account_number: str | None = None
    supplier_bank_account_holder: str | None = None
    supplier_payment_terms: str | None = None
    lines: list[POLineOut] = Field(default_factory=list)
