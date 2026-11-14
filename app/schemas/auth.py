"""Schema Pydantic untuk Autentikasi & Profil Pengguna Aktif (FR-01)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.validation import pydantic_required_str


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=255)

    @field_validator("username")
    @classmethod
    def _clean_username(cls, v: Any) -> str:
        return pydantic_required_str(v, label="Username")


class RefreshTokenRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=512)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)

    @field_validator("new_password")
    @classmethod
    def _non_blank_new_password(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Kata sandi baru tidak boleh hanya berisi spasi.")
        return v


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    access_expires_at: datetime


class MeOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role_id: int
    role_name: str
    is_active: bool
    permissions: list[str]
    warehouse_ids: list[int]
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    message: str

