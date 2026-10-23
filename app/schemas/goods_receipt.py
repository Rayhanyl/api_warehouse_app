"""Schema Pydantic untuk Goods Receipt (GR) dan GR Lines (FR-05, PRD 5.1, 6.2, 6.9)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import DecimalStr


class GRLineInput(BaseModel):
    po_line_id: int
    location_id: int
    qty_received: Decimal
    notes: str | None = None

    @field_validator("qty_received", mode="before")
    @classmethod
    def _reject_float_qty(cls, v: Any) -> Any:
        if isinstance(v, float):
            raise ValueError("Kuantitas tidak boleh bertipe float; gunakan string desimal atau bilangan bulat.")
        return v


class GRLineOut(BaseModel):
    id: int
    gr_id: int
    po_id: int
    warehouse_id: int
    po_line_id: int
    item_id: int
    item_sku: str
    item_name: str
    uom_id: int
    uom_code: str
    allow_decimal: bool
    location_id: int
    location_code: str
    location_name: str
    qty_received: DecimalStr
    notes: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class GoodsReceiptCreate(BaseModel):
    po_id: int
    received_date: date
    notes: str | None = None
    lines: list[GRLineInput] = Field(default_factory=list)


class GoodsReceiptUpdate(BaseModel):
    received_date: date | None = None
    notes: str | None = None
    lines: list[GRLineInput] | None = None


class GoodsReceiptSummaryOut(BaseModel):
    id: int
    gr_number: str
    po_id: int
    po_number: str
    supplier_id: int
    supplier_code: str
    supplier_name: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    status: str
    received_date: date
    notes: str | None = None
    line_count: int = 0
    posted_at: datetime | None = None
    posted_by: int | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class GoodsReceiptOut(GoodsReceiptSummaryOut):
    lines: list[GRLineOut] = Field(default_factory=list)

