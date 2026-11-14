"""Schema Pydantic untuk Master Data: Kategori, UoM, Barang (Item), dan Pemasok (Supplier) (FR-02)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validation import (
    pydantic_optional_non_blank_str,
    pydantic_optional_str,
    pydantic_required_str,
    pydantic_validate_code,
    pydantic_validate_email,
    pydantic_validate_optional_code,
    pydantic_validate_optional_phone,
)


# ============================================================================
# Categories
# ============================================================================
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Nama kategori")

    @field_validator("description")
    @classmethod
    def _val_description(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str | None:
        return pydantic_optional_non_blank_str(v, label="Nama kategori")

    @field_validator("description")
    @classmethod
    def _val_description(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "CategoryUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_active: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Units of Measure (UoM)
# ============================================================================
class UomCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=60)
    allow_decimal: bool = False
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str:
        return pydantic_validate_code(v, label="Kode UoM")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Nama UoM")


class UomUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=60)
    allow_decimal: bool | None = None
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str | None:
        if v is None:
            return None
        return pydantic_validate_code(v, label="Kode UoM")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str | None:
        return pydantic_optional_non_blank_str(v, label="Nama UoM")

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "UomUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


class UomOut(BaseModel):
    id: int
    code: str
    name: str
    allow_decimal: bool
    is_active: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Suppliers
# ============================================================================
class SupplierCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=1000)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str:
        return pydantic_validate_code(v, label="Kode pemasok")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Nama pemasok")

    @field_validator("contact_person", "address")
    @classmethod
    def _val_optional_text(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)

    @field_validator("phone")
    @classmethod
    def _val_phone(cls, v: Any) -> str | None:
        return pydantic_validate_optional_phone(v)

    @field_validator("email")
    @classmethod
    def _val_email(cls, v: Any) -> str | None:
        clean = pydantic_optional_str(v)
        return pydantic_validate_email(clean) if clean is not None else None


class SupplierUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str | None:
        if v is None:
            return None
        return pydantic_validate_code(v, label="Kode pemasok")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str | None:
        return pydantic_optional_non_blank_str(v, label="Nama pemasok")

    @field_validator("contact_person", "address")
    @classmethod
    def _val_optional_text(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)

    @field_validator("phone")
    @classmethod
    def _val_phone(cls, v: Any) -> str | None:
        return pydantic_validate_optional_phone(v)

    @field_validator("email")
    @classmethod
    def _val_email(cls, v: Any) -> str | None:
        clean = pydantic_optional_str(v)
        return pydantic_validate_email(clean) if clean is not None else None

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "SupplierUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


class SupplierOut(BaseModel):
    id: int
    code: str
    name: str
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    is_active: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# Items
# ============================================================================
class ItemCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category_id: int = Field(..., gt=0)
    uom_id: int = Field(..., gt=0)
    is_active: bool = True

    @field_validator("sku")
    @classmethod
    def _val_sku(cls, v: Any) -> str:
        return pydantic_validate_code(v, label="SKU barang")

    @field_validator("barcode")
    @classmethod
    def _val_barcode(cls, v: Any) -> str | None:
        return pydantic_validate_optional_code(v, label="Barcode barang")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Nama barang")

    @field_validator("description")
    @classmethod
    def _val_description(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)


class ItemUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category_id: int | None = Field(default=None, gt=0)
    uom_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None

    @field_validator("sku")
    @classmethod
    def _val_sku(cls, v: Any) -> str | None:
        if v is None:
            return None
        return pydantic_validate_code(v, label="SKU barang")

    @field_validator("barcode")
    @classmethod
    def _val_barcode(cls, v: Any) -> str | None:
        return pydantic_validate_optional_code(v, label="Barcode barang")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str | None:
        return pydantic_optional_non_blank_str(v, label="Nama barang")

    @field_validator("description")
    @classmethod
    def _val_description(cls, v: Any) -> str | None:
        return pydantic_optional_str(v)

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "ItemUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


class ItemOut(BaseModel):
    id: int
    sku: str
    barcode: str | None = None
    name: str
    description: str | None = None
    category_id: int
    category_name: str
    uom_id: int
    uom_code: str
    uom_name: str
    allow_decimal: bool
    is_active: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class ItemImportErrorOut(BaseModel):
    row: int
    field: str
    code: str
    message: str


class ItemImportOut(BaseModel):
    total_rows: int
    imported_count: int
    failed_count: int
    errors: list[ItemImportErrorOut]


class SupplierImportErrorOut(BaseModel):
    row: int
    field: str
    code: str
    message: str


class SupplierImportOut(BaseModel):
    total_rows: int
    imported_count: int
    failed_count: int
    errors: list[SupplierImportErrorOut]

