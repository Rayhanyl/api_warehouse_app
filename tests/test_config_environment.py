"""Pengujian konfigurasi multi-environment: pemilihan berkas env dan guard production."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import ValidationError
import pytest

from app.core import env_files
from app.core.config import Settings
from db import migrate

SAFE_SECRET = "x" * 48
BASE_KWARGS = {
    "_env_file": None,
    "database_url": "postgresql://wms_app:pw@localhost:5432/wms",
}


def _isolated_environ(monkeypatch: pytest.MonkeyPatch, **extra: str) -> None:
    """Mengganti os.environ dengan salinan bersih agar setdefault tidak mencemari proses uji."""
    ignored = {"ENV_FILE", "MIGRATION_DATABASE_URL", "APP_ENV", "DATABASE_URL", "JWT_SECRET"}
    clean = {k: v for k, v in os.environ.items() if k not in ignored}
    clean.update(extra)
    monkeypatch.setattr(os, "environ", clean)


def test_app_env_defaults_to_local_and_accepts_known_values() -> None:
    assert Settings(**BASE_KWARGS, jwt_secret=SAFE_SECRET).app_env == "local"
    assert Settings(**BASE_KWARGS, jwt_secret=SAFE_SECRET, app_env="development").app_env == "development"
    with pytest.raises(ValidationError):
        Settings(**BASE_KWARGS, jwt_secret=SAFE_SECRET, app_env="prod-typo")


def test_production_rejects_insecure_cookie_and_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        Settings(**BASE_KWARGS, jwt_secret=SAFE_SECRET, app_env="production", cookie_secure=False)
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            **BASE_KWARGS,
            jwt_secret="ganti-dengan-string-acak-minimal-32-byte",
            app_env="production",
            cookie_secure=True,
        )


def test_production_accepts_safe_configuration_and_non_production_is_not_blocked() -> None:
    prod = Settings(**BASE_KWARGS, jwt_secret=SAFE_SECRET, app_env="production", cookie_secure=True)
    assert prod.app_env == "production"
    local = Settings(
        **BASE_KWARGS, jwt_secret="ganti-dengan-string-acak-minimal-32-byte", cookie_secure=False
    )
    assert local.cookie_secure is False


def test_resolve_env_files_default_layers_env_then_env_local(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolated_environ(monkeypatch)
    files = env_files.resolve_env_files()
    assert [p.name for p in files] == [".env", ".env.local"]
    assert all(p.parent == env_files.PROJECT_ROOT for p in files)


def test_resolve_env_files_uses_explicit_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "custom.env"
    target.write_text("APP_ENV=development\n", encoding="utf-8")
    _isolated_environ(monkeypatch, ENV_FILE=str(target))
    assert env_files.resolve_env_files() == (target,)


def test_resolve_env_files_fails_fast_when_explicit_file_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolated_environ(monkeypatch, ENV_FILE=str(tmp_path / "tidak-ada.env"))
    with pytest.raises(RuntimeError, match="ENV_FILE"):
        env_files.resolve_env_files()


def test_env_files_with_utf8_bom_are_parsed_by_settings_and_migration_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Berkas yang disimpan Windows dengan BOM tidak boleh merusak baris pertama."""
    target = tmp_path / "bom.env"
    target.write_text(
        "APP_ENV=development\n"
        "DATABASE_URL=postgresql://wms_app:pw@localhost:5432/wms\n"
        "MIGRATION_DATABASE_URL=postgresql://owner:pw@bom-host:5432/wms\n"
        f"JWT_SECRET={SAFE_SECRET}\n",
        encoding="utf-8-sig",
    )
    assert target.read_bytes().startswith(b"\xef\xbb\xbf")

    _isolated_environ(monkeypatch, ENV_FILE=str(target))
    assert Settings(_env_file=target).app_env == "development"
    assert migrate.get_migration_db_url() == "postgresql://owner:pw@bom-host:5432/wms"


def test_migration_runner_honours_env_file_but_never_overrides_os_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "dev.env"
    target.write_text(
        "MIGRATION_DATABASE_URL=postgresql://owner:pw@dev-tunnel:15432/wms  # komentar\n",
        encoding="utf-8",
    )
    _isolated_environ(monkeypatch, ENV_FILE=str(target))
    assert migrate.get_migration_db_url() == "postgresql://owner:pw@dev-tunnel:15432/wms"

    _isolated_environ(
        monkeypatch,
        ENV_FILE=str(target),
        MIGRATION_DATABASE_URL="postgresql://owner:pw@dari-os:5432/wms",
    )
    assert migrate.get_migration_db_url() == "postgresql://owner:pw@dari-os:5432/wms"
