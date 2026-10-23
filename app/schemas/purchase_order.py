"""Schema Pydantic untuk Purchase Order (PO) dan PO Lines (FR-04, PRD 5.1, 6.9)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import DecimalStr


class POLineInput(BaseModel):
    item_id: int
    qty_ordered: Decimal
    notes: str | None = None

    @field_validator("qty_ordered", mode="before")
    @classmethod
    def _reject_float_qty(cls, v: Any) -> Any:
        if isinstance(v, float):
            raise ValueError("Kuantitas tidak boleh bertipe float; gunakan string desimal atau bilangan bulat.")
        return v


class POLineOut(BaseModel):
    id: int
    po_id: int
    item_id: int
    item_sku: str
    item_name: str
    uom_id: int
    uom_code: str
    allow_decimal: bool
    qty_ordered: DecimalStr
    qty_received: DecimalStr
    notes: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    warehouse_id: int
    order_date: date
    notes: str | None = None
    lines: list[POLineInput] = Field(default_factory=list)


class PurchaseOrderUpdate(BaseModel):
    supplier_id: int | None = None
    warehouse_id: int | None = None
    order_date: date | None = None
    notes: str | None = None
    lines: list[POLineInput] | None = None


class PurchaseOrderCloseRequest(BaseModel):
    closed_reason: str = Field(..., min_length=1)


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
    lines: list[POLineOut] = Field(default_factory=list)

