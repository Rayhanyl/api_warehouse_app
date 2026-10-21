"""Konfigurasi aplikasi WMS API berbasis variabel lingkungan (.env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WMS REST API"
    app_version: str = "2.0.0"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql://postgres:123456@127.0.0.1:5432/warehouse_db"
    migration_database_url: str | None = None
    test_database_url: str | None = None

    jwt_secret: str = "4a8d69d66e26f569dcb1c00dda29951a31c48f2886d901cb2a1ee03b91816da9"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    login_max_attempts: int = 5
    login_lock_minutes: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

