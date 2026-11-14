"""Konfigurasi aplikasi WMS API berbasis variabel lingkungan (.env) sesuai PRD 7.2 & AGENTS.md §6."""

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.env_files import resolve_env_files

# Placeholder yang ada di berkas contoh; tidak boleh dipakai di production.
_PLACEHOLDER_JWT_MARKERS = ("ganti-dengan", "change_me", "changeme")


class Settings(BaseSettings):
    app_name: str = "WMS REST API"
    app_version: str = "2.0.0"
    api_v1_prefix: str = "/api/v1"

    app_env: Literal["local", "development", "staging", "production"] = Field(
        default="local",
        description="Nama lingkungan aktif; dipakai untuk label log/alert dan guard production",
    )

    # Kredensial database dan rahasia JWT wajib berasal dari environment / .env (tanpa rahasia di kode)
    database_url: str = Field(..., description="URL koneksi PostgreSQL untuk aplikasi")
    migration_database_url: str | None = None
    test_database_url: str | None = None

    jwt_secret: str = Field(..., min_length=32, description="Kunci rahasia penandatanganan JWT HS256")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    login_max_attempts: int = 5
    login_lock_minutes: int = 15

    frontend_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        description="Daftar origin frontend yang diizinkan oleh CORS",
    )
    cookie_secure: bool = Field(
        default=False,
        description="Flag Secure untuk cookie refresh token (True di HTTPS production)",
    )
    cookie_samesite: str = Field(
        default="lax",
        description="Nilai SameSite untuk cookie refresh token (lax / strict / none)",
    )
    trusted_proxy_ips: list[str] = Field(default_factory=list)

    # Notifikasi error real-time via Telegram Bot HTTP API (Tahap 13 / Poin 6)
    telegram_enabled: bool = Field(
        default=False,
        description="Aktifkan pengiriman notifikasi error real-time ke Telegram",
    )
    telegram_bot_token: str | None = Field(
        default=None,
        description="Token Bot Telegram HTTP API (simpan hanya di .env aktif, jangan di Git)",
    )
    telegram_chat_id: str | None = Field(
        default=None,
        description="Chat ID / Group ID Telegram penerima notifikasi error",
    )
    telegram_thread_id: int | None = Field(
        default=None,
        description="Opsional: message_thread_id untuk grup Telegram bertopik",
    )
    telegram_timeout_seconds: float = Field(
        default=5.0,
        ge=0.5,
        le=30.0,
        description="Timeout permintaan HTTP ke API Telegram (detik)",
    )
    telegram_cooldown_seconds: int = Field(
        default=60,
        ge=0,
        le=3600,
        description="Jeda cooldown deduplikasi per signature error (detik) agar bebas rate-limit",
    )

    @field_validator("telegram_bot_token", "telegram_chat_id", "telegram_thread_id", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # Berkas env dipilih oleh `resolve_env_files()` (default `.env` + `.env.local`,
    # atau satu berkas eksplisit lewat variabel OS `ENV_FILE`).
    model_config = SettingsConfigDict(
        env_file=resolve_env_files(),
        env_file_encoding="utf-8-sig",  # toleran BOM (Notepad / PowerShell 5.1 di Windows)
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _enforce_production_guards(self) -> "Settings":
        """Menolak konfigurasi production yang jelas tidak aman agar gagal saat startup."""
        if self.app_env != "production":
            return self
        problems: list[str] = []
        if any(marker in self.jwt_secret.lower() for marker in _PLACEHOLDER_JWT_MARKERS):
            problems.append("JWT_SECRET masih berisi placeholder dari berkas contoh")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE wajib True saat APP_ENV=production")
        if problems:
            raise ValueError("Konfigurasi production tidak aman: " + "; ".join(problems))
        return self


settings = Settings()
