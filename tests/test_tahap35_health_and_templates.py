"""Pengujian Tahap 35: schema migration readiness & 503 guard pada document templates."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
import psycopg
import pytest

from app.core import database as db_module
from app.repositories import document_template_repo


def test_health_reports_schema_ok_when_migrations_current(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["schema_status"] == "ok"
    assert payload["pending_migrations"] == []


def test_health_reports_degraded_when_pending_migrations_exist(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.check_schema_health",
        lambda: (True, ["015_create_document_templates_table.sql"]),
    )

    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["schema_status"] == "pending_migrations"
    assert payload["pending_migrations"] == ["015_create_document_templates_table.sql"]


def test_document_templates_returns_503_when_table_missing(
    client: TestClient,
    superadmin_user: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_undefined_table(*_args: object, **_kwargs: object) -> list[dict]:
        raise psycopg.errors.UndefinedTable('relation "document_templates" does not exist')

    class _FakeConn:
        def execute(self, *_args: object, **_kwargs: object) -> object:
            _raise_undefined_table()

    with pytest.raises(document_template_repo.SchemaMigrationRequiredError) as exc_info:
        document_template_repo.list_templates(_FakeConn())  # type: ignore[arg-type]
    assert exc_info.value.http_status == 503
    assert exc_info.value.code == "SCHEMA_MIGRATION_REQUIRED"

    # Pastikan via endpoint mengembalikan HTTP 503 terstruktur, bukan 500 mentah
    monkeypatch.setattr(
        "app.services.document_template_service.document_template_repo.list_templates",
        lambda _conn: (_ for _ in ()).throw(
            document_template_repo.SchemaMigrationRequiredError(
                "Tabel document_templates belum dimigrasi.",
                details={"table": "document_templates"},
            )
        ),
    )
    response = client.get(
        "/api/v1/document-templates",
        headers=superadmin_user["auth_headers"],
    )
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "SCHEMA_MIGRATION_REQUIRED"


def test_list_pending_migrations_returns_empty_on_test_db(
    db_conn: psycopg.Connection[dict[str, Any]],
) -> None:
    pending = db_module.list_pending_migrations(db_conn)
    assert pending == []
