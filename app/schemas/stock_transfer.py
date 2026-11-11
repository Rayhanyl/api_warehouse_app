"""Schema Pydantic untuk Stock Transfer dan barisnya (FR-06, PRD 5.1, 6.3, 6.7, 6.9)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import DecimalStr


def _reject_float(v: Any) -> Any:
    if isinstance(v, float):
        raise ValueError("Kuantitas tidak boleh bertipe float; gunakan string desimal atau bilangan bulat.")
    return v


class StockTransferLineInput(BaseModel):
    item_id: int = Field(..., gt=0)
    qty: Decimal

    @field_validator("qty", mode="before")
    @classmethod
    def _reject_float_qty(cls, v: Any) -> Any:
        return _reject_float(v)


class StockTransferLineOut(BaseModel):
    id: int
    transfer_id: int
    item_id: int
    item_sku: str
    item_barcode: str | None = None
    item_name: str
    uom_id: int
    uom_code: str
    allow_decimal: bool
    qty: DecimalStr
    qty_received: DecimalStr | None = None
    qty_variance: DecimalStr | None = None
    variance_reason: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class StockTransferCreate(BaseModel):
    source_warehouse_id: int = Field(..., gt=0)
    source_location_id: int = Field(..., gt=0)
    destination_warehouse_id: int = Field(..., gt=0)
    destination_location_id: int = Field(..., gt=0)
    notes: str | None = Field(default=None, max_length=1000)
    lines: list[StockTransferLineInput] = Field(default_factory=list)


class StockTransferUpdate(BaseModel):
    source_warehouse_id: int | None = Field(default=None, gt=0)
    source_location_id: int | None = Field(default=None, gt=0)
    destination_warehouse_id: int | None = Field(default=None, gt=0)
    destination_location_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=1000)
    lines: list[StockTransferLineInput] | None = None

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "StockTransferUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


class StockTransferReceiveLine(BaseModel):
    line_id: int = Field(..., gt=0)
    qty_received: Decimal
    variance_reason: str | None = Field(default=None, max_length=500)

    @field_validator("qty_received", mode="before")
    @classmethod
    def _reject_float_qty(cls, v: Any) -> Any:
        return _reject_float(v)


class StockTransferReceive(BaseModel):
    lines: list[StockTransferReceiveLine] = Field(min_length=1)


class StockTransferSummaryOut(BaseModel):
    id: int
    transfer_number: str
    source_warehouse_id: int
    source_warehouse_code: str
    source_warehouse_name: str
    source_location_id: int
    source_location_code: str
    destination_warehouse_id: int
    destination_warehouse_code: str
    destination_warehouse_name: str
    destination_location_id: int
    destination_location_code: str
    status: str
    notes: str | None = None
    line_count: int = 0
    approved_by: int | None = None
    approved_at: datetime | None = None
    shipped_by: int | None = None
    shipped_at: datetime | None = None
    received_by: int | None = None
    received_at: datetime | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class StockTransferOut(StockTransferSummaryOut):
    lines: list[StockTransferLineOut] = Field(default_factory=list)

