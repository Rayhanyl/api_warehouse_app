"""Schema Pydantic untuk Master Data: Kategori, UoM, Barang (Item), dan Pemasok (Supplier) (FR-02)."""

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================================
# Categories
# ============================================================================
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    is_active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    is_active: bool | None = None


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


class UomUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=60)
    allow_decimal: bool | None = None
    is_active: bool | None = None


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
    address: str | None = None
    is_active: bool = True


class SupplierUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    is_active: bool | None = None


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
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    category_id: int
    uom_id: int
    is_active: bool = True


class ItemUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category_id: int | None = None
    uom_id: int | None = None
    is_active: bool | None = None


class ItemOut(BaseModel):
    id: int
    sku: str
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

