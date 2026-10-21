"""Schema Pydantic untuk Gudang (Warehouse) dan Lokasi Penyimpanan (Storage Location) (FR-02)."""

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================================
# Warehouses
# ============================================================================
class WarehouseCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    address: str | None = None
    allow_negative_stock: bool = False
    is_active: bool = True


class WarehouseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = None
    allow_negative_stock: bool | None = None
    is_active: bool | None = None


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
    warehouse_id: int
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=120)
    is_active: bool = True


class WarehouseLocationCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=120)
    is_active: bool = True


class StorageLocationUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None


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

