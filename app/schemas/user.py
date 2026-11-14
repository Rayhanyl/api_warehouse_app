"""Schema Pydantic untuk Manajemen Pengguna, Role/Permission, dan Penugasan Gudang (Bagian 3 PRD)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validation import (
    pydantic_optional_non_blank_str,
    pydantic_required_str,
    pydantic_validate_email,
    pydantic_validate_positive_id_list,
    pydantic_validate_username,
)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=150)
    role_id: int = Field(..., gt=0)
    is_active: bool = True
    warehouse_ids: list[int] = Field(default_factory=list)

    @field_validator("username")
    @classmethod
    def _val_username(cls, v: Any) -> str:
        return pydantic_validate_username(v)

    @field_validator("email")
    @classmethod
    def _val_email(cls, v: Any) -> str:
        return pydantic_validate_email(v)

    @field_validator("password")
    @classmethod
    def _val_password(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Kata sandi tidak boleh hanya berisi spasi.")
        return v

    @field_validator("full_name")
    @classmethod
    def _val_full_name(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Nama lengkap")

    @field_validator("warehouse_ids")
    @classmethod
    def _val_warehouse_ids(cls, v: list[int]) -> list[int]:
        return pydantic_validate_positive_id_list(v, label="Daftar gudang") or []


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    role_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=255)

    @field_validator("email")
    @classmethod
    def _val_email(cls, v: Any) -> str | None:
        return pydantic_validate_email(v)

    @field_validator("full_name")
    @classmethod
    def _val_full_name(cls, v: Any) -> str | None:
        return pydantic_optional_non_blank_str(v, label="Nama lengkap")

    @field_validator("password")
    @classmethod
    def _val_password(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Kata sandi tidak boleh hanya berisi spasi.")
        return v

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


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

    @field_validator("warehouse_ids")
    @classmethod
    def _val_warehouse_ids(cls, v: list[int]) -> list[int]:
        return pydantic_validate_positive_id_list(v, label="Daftar gudang") or []


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

