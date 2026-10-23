"""Schema Pydantic untuk Stock Opname dan baris hasil hitung fisiknya (FR-07, PRD 5.1, 6.6, 6.9)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import DecimalStr


def _reject_float(v: Any) -> Any:
    if isinstance(v, float):
        raise ValueError(
            "Kuantitas tidak boleh bertipe float; gunakan string desimal atau bilangan bulat."
        )
    return v


class StockOpnameCreate(BaseModel):
    warehouse_id: int
    location_id: int | None = None
    notes: str | None = None


class StockOpnameUpdate(BaseModel):
    location_id: int | None = None
    clear_location: bool = False
    notes: str | None = None


class StockOpnameCountLineInput(BaseModel):
    line_id: int | None = None
    location_id: int | None = None
    item_id: int | None = None
    qty_physical: Decimal
    notes: str | None = None

    @field_validator("qty_physical", mode="before")
    @classmethod
    def _reject_float_qty(cls, v: Any) -> Any:
        return _reject_float(v)


class StockOpnameCountRequest(BaseModel):
    lines: list[StockOpnameCountLineInput] = Field(min_length=1)


class StockOpnameRejectRequest(BaseModel):
    rejection_reason: str


class StockOpnameLineOut(BaseModel):
    id: int
    opname_id: int
    warehouse_id: int
    location_id: int
    location_code: str
    location_name: str
    item_id: int
    item_sku: str
    item_name: str
    uom_id: int
    uom_code: str
    allow_decimal: bool
    qty_system: DecimalStr
    qty_physical: DecimalStr | None = None
    qty_variance: DecimalStr | None = None
    counted_by: int | None = None
    counted_at: datetime | None = None
    notes: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class StockOpnameSummaryOut(BaseModel):
    id: int
    opname_number: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    location_id: int | None = None
    location_code: str | None = None
    location_name: str | None = None
    status: str
    notes: str | None = None
    line_count: int = 0
    started_at: datetime | None = None
    started_by: int | None = None
    submitted_at: datetime | None = None
    submitted_by: int | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class StockOpnameOut(StockOpnameSummaryOut):
    lines: list[StockOpnameLineOut] = Field(default_factory=list)

