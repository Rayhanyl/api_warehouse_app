"""Konfigurasi pytest untuk pengujian terhadap database PostgreSQL sungguhan (wms_test)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from urllib.parse import urlparse, urlunparse

from fastapi.testclient import TestClient
import psycopg
from psycopg.rows import dict_row
import pytest

from app.core import database as db_module
from app.core.config import settings
from app.main import app
from db.migrate import run_migrations
from tests import factories


def _get_safe_test_db_url() -> str:
    """Memastikan URL database uji selalu mengarah ke database `wms_test` (AGENTS.md Bagian 7)."""
    test_url = settings.test_database_url
    if not test_url:
        raise RuntimeError("TEST_DATABASE_URL wajib diatur untuk menjalankan pytest.")
    parsed = urlparse(test_url)
    db_name = parsed.path.lstrip("/")
    if db_name != "wms_test":
        raise RuntimeError(
            f"Keamanan pengujian: TEST_DATABASE_URL harus mengarah ke 'wms_test', bukan '{db_name}'."
        )
    return test_url


def _ensure_test_database_exists(test_url: str) -> None:
    """Membuat database `wms_test` secara otomatis bila belum tersedia di PostgreSQL lokal."""
    try:
        with psycopg.connect(test_url, autocommit=True):
            return
    except psycopg.OperationalError:
        pass

    admin_url = settings.migration_database_url or settings.database_url
    with psycopg.connect(admin_url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'wms_test'"
        ).fetchone()
        if not row:
            conn.execute("CREATE DATABASE wms_test")


@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[str, None, None]:
    """Menyiapkan database `wms_test`, menerapkan migrasi 001-008, dan mengarahkan pool aplikasi ke `wms_test`."""
    test_url = _get_safe_test_db_url()
    _ensure_test_database_exists(test_url)
    run_migrations(test_url)

    # Arahkan connection pool aplikasi ke wms_test
    db_module.close_pool()
    db_module.open_pool(test_url)
    try:
        yield test_url
    finally:
        db_module.close_pool()


@pytest.fixture(autouse=True)
def reset_test_data(setup_test_database: str) -> Generator[None, None, None]:
    """Mereset data operasional di `wms_test` antar pengujian sambil mempertahankan seed roles & permissions."""
    with psycopg.connect(setup_test_database, autocommit=True, row_factory=dict_row) as conn:
        conn.execute(
            """
            TRUNCATE TABLE
                audit_logs,
                document_sequences,
                stock_opname_lines,
                stock_opnames,
                stock_transfer_lines,
                stock_transfers,
                gr_lines,
                goods_receipts,
                po_lines,
                purchase_orders,
                stock_movements,
                inventory_balances,
                storage_locations,
                user_warehouses,
                warehouses,
                items,
                suppliers,
                uoms,
                categories,
                refresh_tokens,
                users
            RESTART IDENTITY CASCADE
            """
        )
        # Put test-created nodes at the root before deleting so self-FK RESTRICT
        # does not depend on row deletion order.
        conn.execute("UPDATE menus SET parent_id = NULL WHERE created_by IS NOT NULL")
        conn.execute("DELETE FROM menus WHERE created_by IS NOT NULL")
        conn.execute("UPDATE menus SET is_active = TRUE WHERE created_by IS NULL")
    yield


@pytest.fixture()
def db_conn(setup_test_database: str) -> Generator[psycopg.Connection[dict[str, Any]], None, None]:
    """Koneksi langsung ke `wms_test` untuk setup data fixture dan verifikasi assertion."""
    with psycopg.connect(setup_test_database, autocommit=True, row_factory=dict_row) as conn:
        yield conn


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """HTTP TestClient FastAPI yang terhubung ke `wms_test`."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def superadmin_user(db_conn: psycopg.Connection[dict[str, Any]]) -> dict[str, Any]:
    return factories.create_user(
        db_conn,
        username="superadmin",
        email="superadmin@wms.test",
        password="Password123!",
        full_name="Super Admin User",
        role_name="Super Admin",
    )


@pytest.fixture()
def manager_user(db_conn: psycopg.Connection[dict[str, Any]]) -> dict[str, Any]:
    return factories.create_user(
        db_conn,
        username="manager1",
        email="manager1@wms.test",
        password="Password123!",
        full_name="Warehouse Manager User",
        role_name="Warehouse Manager",
    )


@pytest.fixture()
def purchasing_user(db_conn: psycopg.Connection[dict[str, Any]]) -> dict[str, Any]:
    return factories.create_user(
        db_conn,
        username="purchasing1",
        email="purchasing1@wms.test",
        password="Password123!",
        full_name="Purchasing Staff User",
        role_name="Purchasing Staff",
    )


@pytest.fixture()
def staff_user(db_conn: psycopg.Connection[dict[str, Any]]) -> dict[str, Any]:
    return factories.create_user(
        db_conn,
        username="staff1",
        email="staff1@wms.test",
        password="Password123!",
        full_name="Warehouse Staff User",
        role_name="Warehouse Staff",
    )


@pytest.fixture()
def auditor_user(db_conn: psycopg.Connection[dict[str, Any]]) -> dict[str, Any]:
    return factories.create_user(
        db_conn,
        username="auditor1",
        email="auditor1@wms.test",
        password="Password123!",
        full_name="Auditor User",
        role_name="Auditor",
    )
