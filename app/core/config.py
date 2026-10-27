"""Konfigurasi aplikasi WMS API berbasis variabel lingkungan (.env) sesuai PRD 7.2 & AGENTS.md §6."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WMS REST API"
    app_version: str = "2.0.0"
    api_v1_prefix: str = "/api/v1"

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
        default_factory=lambda: ["http://localhost:5173"],
        description="Daftar origin frontend yang diizinkan oleh CORS",
    )
    trusted_proxy_ips: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
