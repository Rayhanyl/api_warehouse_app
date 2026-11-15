"""Schema Pydantic untuk pengaturan sistem & ambang approval (Tahap 34)."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import MoneyStr


class ApprovalSettingsOut(BaseModel):
    po_l2_approval_threshold: MoneyStr
    description: str | None = None
    updated_by: int | None = None
    updated_by_name: str | None = None
    updated_at: datetime | None = None


class ApprovalSettingsUpdate(BaseModel):
    po_l2_approval_threshold: Decimal = Field(..., description="Ambang nominal total PO wajib persetujuan Level 2 (IDR)")

    @field_validator("po_l2_approval_threshold", mode="before")
    @classmethod
    def _validate_threshold(cls, v: Any) -> Decimal:
        if v is None or v == "":
            raise ValueError("Ambang nominal approval PO wajib diisi.")
        try:
            dec = Decimal(str(v).strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Ambang nominal approval PO harus berupa angka yang valid.") from exc
        if dec < Decimal("0"):
            raise ValueError("Ambang nominal approval PO tidak boleh negatif.")
        return dec.quantize(Decimal("0.01"))
