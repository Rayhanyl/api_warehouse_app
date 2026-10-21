"""Helper pembuatan data uji (user, gudang, lokasi, penugasan gudang) pada database `wms_test`."""

from __future__ import annotations

from typing import Any

from psycopg import Connection

from app.core.security import create_access_token, hash_password
from app.repositories import permission_repo, user_repo


def create_user(
    conn: Connection[dict[str, Any]],
    *,
    username: str,
    email: str,
    password: str = "Password123!",
    full_name: str = "Test User",
    role_name: str = "Warehouse Staff",
    is_active: bool = True,
    warehouse_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Membuat pengguna uji beserta token akses JWT siap pakai."""
    role = permission_repo.get_role_by_name(conn, role_name)
    assert role is not None, f"Role '{role_name}' tidak ditemukan di wms_test"

    created = user_repo.insert_user(
        conn,
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role_id=int(role["id"]),
        is_active=is_active,
        created_by=None,
    )
    if warehouse_ids:
        permission_repo.update_user_warehouses(
            conn,
            user_id=int(created["id"]),
            warehouse_ids=warehouse_ids,
            actor_id=int(created["id"]),
        )
        created = user_repo.get_user_auth_context(conn, int(created["id"]))
        assert created is not None

    access_token, _ = create_access_token(int(created["id"]))
    created["plain_password"] = password
    created["access_token"] = access_token
    created["auth_headers"] = {"Authorization": f"Bearer {access_token}"}
    return created


def create_warehouse(
    conn: Connection[dict[str, Any]],
    *,
    code: str = "WH-A",
    name: str = "Gudang A",
    allow_negative_stock: bool = False,
    is_active: bool = True,
) -> dict[str, Any]:
    """Membuat gudang uji di database `wms_test`."""
    row = conn.execute(
        """
        INSERT INTO warehouses (code, name, allow_negative_stock, is_active)
        VALUES (%s, %s, %s, %s)
        RETURNING id, code, name, allow_negative_stock, is_active, created_at, updated_at
        """,
        (code, name, allow_negative_stock, is_active),
    ).fetchone()
    assert row is not None
    return row


def create_location(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    code: str = "RACK-A1",
    name: str = "Rak A1",
    is_active: bool = True,
) -> dict[str, Any]:
    """Membuat lokasi penyimpanan uji di database `wms_test`."""
    row = conn.execute(
        """
        INSERT INTO storage_locations (warehouse_id, code, name, is_active)
        VALUES (%s, %s, %s, %s)
        RETURNING id, warehouse_id, code, name, is_active, created_at, updated_at
        """,
        (warehouse_id, code, name, is_active),
    ).fetchone()
    assert row is not None
    return row


def create_category(
    conn: Connection[dict[str, Any]],
    *,
    name: str = "Elektronik",
    description: str | None = "Kategori Elektronik",
    is_active: bool = True,
) -> dict[str, Any]:
    """Membuat kategori barang uji di database `wms_test`."""
    row = conn.execute(
        """
        INSERT INTO categories (name, description, is_active)
        VALUES (%s, %s, %s)
        RETURNING id, name, description, is_active, created_at, updated_at
        """,
        (name, description, is_active),
    ).fetchone()
    assert row is not None
    return row


def create_uom(
    conn: Connection[dict[str, Any]],
    *,
    code: str = "PCS",
    name: str = "Pieces",
    allow_decimal: bool = False,
    is_active: bool = True,
) -> dict[str, Any]:
    """Membuat UoM uji di database `wms_test`."""
    row = conn.execute(
        """
        INSERT INTO uoms (code, name, allow_decimal, is_active)
        VALUES (%s, %s, %s, %s)
        RETURNING id, code, name, allow_decimal, is_active, created_at, updated_at
        """,
        (code, name, allow_decimal, is_active),
    ).fetchone()
    assert row is not None
    return row


def create_supplier(
    conn: Connection[dict[str, Any]],
    *,
    code: str = "SUP-01",
    name: str = "PT Pemasok Utama",
    is_active: bool = True,
) -> dict[str, Any]:
    """Membuat pemasok uji di database `wms_test`."""
    row = conn.execute(
        """
        INSERT INTO suppliers (code, name, is_active)
        VALUES (%s, %s, %s)
        RETURNING id, code, name, is_active, created_at, updated_at
        """,
        (code, name, is_active),
    ).fetchone()
    assert row is not None
    return row


def create_item(
    conn: Connection[dict[str, Any]],
    *,
    sku: str = "SKU-001",
    name: str = "Barang Uji 001",
    category_id: int,
    uom_id: int,
    is_active: bool = True,
) -> dict[str, Any]:
    """Membuat barang uji di database `wms_test`."""
    row = conn.execute(
        """
        INSERT INTO items (sku, name, category_id, uom_id, is_active)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, sku, name, category_id, uom_id, is_active, created_at, updated_at
        """,
        (sku, name, category_id, uom_id, is_active),
    ).fetchone()
    assert row is not None
    return row


