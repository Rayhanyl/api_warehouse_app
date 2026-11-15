"""Schema Pydantic untuk Stock Opname dan baris hasil hitung fisiknya (FR-07, PRD 5.1, 6.6, 6.9)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validation import (
    pydantic_optional_str,
    pydantic_required_str,
    pydantic_validate_decimal_qty,
)
from app.schemas.common import ApprovalLogOut, DecimalStr


class StockOpnameCreate(BaseModel):
    warehouse_id: int = Field(..., gt=0)
    location_id: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("notes")
    @classmethod
    def _val_notes(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)


class StockOpnameUpdate(BaseModel):
    location_id: int | None = Field(default=None, gt=0)
    clear_location: bool = False
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("notes")
    @classmethod
    def _val_notes(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "StockOpnameUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


class StockOpnameCountLineInput(BaseModel):
    line_id: int | None = Field(default=None, gt=0)
    location_id: int | None = Field(default=None, gt=0)
    item_id: int | None = Field(default=None, gt=0)
    qty_physical: Decimal
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("qty_physical", mode="before")
    @classmethod
    def _validate_qty_physical(cls, v: Any) -> Decimal:
        return pydantic_validate_decimal_qty(v, label="Jumlah fisik", allow_zero=True)

    @field_validator("notes")
    @classmethod
    def _val_notes(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)


class StockOpnameCountRequest(BaseModel):
    lines: list[StockOpnameCountLineInput] = Field(min_length=1)


class StockOpnameRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("rejection_reason")
    @classmethod
    def _val_rejection_reason(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Alasan penolakan")


class StockOpnameLineOut(BaseModel):
    id: int
    opname_id: int
    warehouse_id: int
    location_id: int
    location_code: str
    location_name: str
    item_id: int
    item_sku: str
    item_barcode: str | None = None
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
    l1_approved_by: int | None = None
    l1_approved_at: datetime | None = None
    l2_approved_by: int | None = None
    l2_approved_at: datetime | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


class StockOpnameOut(StockOpnameSummaryOut):
    lines: list[StockOpnameLineOut] = Field(default_factory=list)
    approval_logs: list[ApprovalLogOut] = Field(default_factory=list)

