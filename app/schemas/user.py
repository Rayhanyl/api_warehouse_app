"""Schema Pydantic untuk Manajemen Pengguna, Role/Permission, dan Penugasan Gudang (Bagian 3 PRD)."""

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=150)
    role_id: int
    is_active: bool = True
    warehouse_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    role_id: int | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=255)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role_id: int
    role_name: str
    is_active: bool
    warehouse_ids: list[int] = Field(default_factory=list)
    failed_login_count: int = 0
    locked_until: datetime | None = None
    last_login_at: datetime | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class UserWarehouseSet(BaseModel):
    warehouse_ids: list[int] = Field(default_factory=list)


class UserWarehouseOut(BaseModel):
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    is_active: bool
    created_by: int | None = None
    created_at: datetime


class PermissionOut(BaseModel):
    id: int
    code: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class RoleOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RolePermissionSet(BaseModel):
    permissions: list[str] = Field(default_factory=list)

