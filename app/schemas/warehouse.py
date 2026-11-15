"""Schema Pydantic untuk Gudang (Warehouse) dan Lokasi Penyimpanan (Storage Location) (FR-02)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validation import (
    pydantic_optional_non_blank_str,
    pydantic_optional_str,
    pydantic_required_str,
    pydantic_validate_code,
)


# ============================================================================
# Warehouses
# ============================================================================
class WarehouseCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=1000)
    allow_negative_stock: bool = False
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str:
        return pydantic_validate_code(v, label="Kode gudang")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Nama gudang")

    @field_validator("address")
    @classmethod
    def _val_address(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)


class WarehouseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=1000)
    allow_negative_stock: bool | None = None
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str | None:
        if v is None:
            return None
        return pydantic_validate_code(v, label="Kode gudang")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str | None:
        return pydantic_optional_non_blank_str(v, label="Nama gudang")

    @field_validator("address")
    @classmethod
    def _val_address(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "WarehouseUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


class WarehouseOut(BaseModel):
    id: int
    code: str
    name: str
    address: str | None = None
    allow_negative_stock: bool
    is_active: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Storage Locations (Bins / Racks)
# ============================================================================
class StorageLocationCreate(BaseModel):
    warehouse_id: int = Field(..., gt=0)
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=120)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str:
        return pydantic_validate_code(v, label="Kode lokasi penyimpanan")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Nama lokasi penyimpanan")


class WarehouseLocationCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=120)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str:
        return pydantic_validate_code(v, label="Kode lokasi penyimpanan")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Nama lokasi penyimpanan")


class StorageLocationUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str | None:
        if v is None:
            return None
        return pydantic_validate_code(v, label="Kode lokasi penyimpanan")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str | None:
        return pydantic_optional_non_blank_str(v, label="Nama lokasi penyimpanan")

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "StorageLocationUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


class StorageLocationOut(BaseModel):
    id: int
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    code: str
    name: str
    is_active: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

