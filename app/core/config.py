"""Konfigurasi aplikasi WMS API berbasis variabel lingkungan (.env) sesuai PRD 7.2 & AGENTS.md §6."""

from typing import Literal

from pydantic import Field, model_validator
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
