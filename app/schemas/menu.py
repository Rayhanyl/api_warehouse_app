"""Schema Pydantic untuk Menu Navigasi Dinamis (FR-01, PRD Lampiran A & C)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MenuCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    path: str = Field(..., min_length=1, max_length=150)
    icon: str | None = Field(default=None, max_length=50)
    parent_id: int | None = None
    sort_order: int = 0
    permission_id: int | None = None
    is_active: bool = True


class MenuUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    path: str | None = Field(default=None, min_length=1, max_length=150)
    icon: str | None = Field(default=None, max_length=50)
    parent_id: int | None = None
    clear_parent: bool = False
    sort_order: int | None = None
    permission_id: int | None = None
    clear_permission: bool = False
    is_active: bool | None = None


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
