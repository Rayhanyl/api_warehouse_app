"""Schema Pydantic untuk Menu Navigasi Dinamis (FR-01, PRD Lampiran A & C)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validation import (
    pydantic_optional_non_blank_str,
    pydantic_required_str,
    pydantic_validate_code,
    pydantic_validate_icon,
    pydantic_validate_menu_path,
    pydantic_validate_optional_code,
)


class MenuCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    path: str = Field(..., min_length=1, max_length=150)
    icon: str | None = Field(default=None, max_length=50)
    parent_id: int | None = Field(default=None, gt=0)
    sort_order: int = Field(default=0, ge=0, le=10000)
    permission_id: int | None = Field(default=None, gt=0)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str:
        return pydantic_validate_code(v, label="Kode menu")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Nama menu")

    @field_validator("path")
    @classmethod
    def _val_path(cls, v: Any) -> str:
        return pydantic_validate_menu_path(v)

    @field_validator("icon")
    @classmethod
    def _val_icon(cls, v: Any) -> str | None:
        return pydantic_validate_icon(v)


class MenuUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    path: str | None = Field(default=None, min_length=1, max_length=150)
    icon: str | None = Field(default=None, max_length=50)
    parent_id: int | None = Field(default=None, gt=0)
    clear_parent: bool = False
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    permission_id: int | None = Field(default=None, gt=0)
    clear_permission: bool = False
    is_active: bool | None = None

    @field_validator("code")
    @classmethod
    def _val_code(cls, v: Any) -> str | None:
        if v is None:
            return None
        clean = pydantic_optional_non_blank_str(v, label="Kode menu")
        return pydantic_validate_optional_code(clean, label="Kode menu")

    @field_validator("name")
    @classmethod
    def _val_name(cls, v: Any) -> str | None:
        return pydantic_optional_non_blank_str(v, label="Nama menu")

    @field_validator("path")
    @classmethod
    def _val_path(cls, v: Any) -> str | None:
        if v is None:
            return None
        return pydantic_validate_menu_path(v)

    @field_validator("icon")
    @classmethod
    def _val_icon(cls, v: Any) -> str | None:
        return pydantic_validate_icon(v)

    @model_validator(mode="after")
    def _ensure_non_empty_patch(self) -> MenuUpdate:
        if not self.model_fields_set:
            raise ValueError("Minimal satu field harus dikirim untuk pembaruan data.")
        return self


class MenuOut(BaseModel):
    id: int
    code: str
    name: str
    path: str
    icon: str | None = None
    parent_id: int | None = None
    parent_code: str | None = None
    parent_name: str | None = None
    sort_order: int
    permission_id: int | None = None
    permission_code: str | None = None
    is_active: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class MenuTreeOut(BaseModel):
    id: int
    code: str
    name: str
    path: str
    icon: str | None = None
    parent_id: int | None = None
    sort_order: int
    permission_code: str | None = None
    is_active: bool
    is_visible: bool
    menu_type: str
    children: list[MenuTreeOut] = Field(default_factory=list)


MenuTreeOut.model_rebuild()
