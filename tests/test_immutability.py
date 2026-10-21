"""Pengujian Imutabilitas Buku Besar & Audit Log (AC-08 & PRD 6.4)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import urlparse, urlunparse

import psycopg
from psycopg.rows import dict_row
import pytest

from app.services import audit_service
from tests import factories


def _ensure_wms_app_role_and_get_url(owner_conn: psycopg.Connection[dict[str, Any]], test_url: str) -> str:
    """Memastikan role `wms_app` tersedia dan hak aksesnya pada `wms_test` sesuai 007_append_only_guards.sql."""
    owner_conn.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wms_app') THEN
                CREATE ROLE wms_app WITH LOGIN PASSWORD 'wms_app_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE;
            ELSE
                ALTER ROLE wms_app WITH LOGIN PASSWORD 'wms_app_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )
    owner_conn.execute("GRANT CONNECT ON DATABASE wms_test TO wms_app")
    owner_conn.execute("GRANT USAGE ON SCHEMA public TO wms_app")
    owner_conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO wms_app")
    owner_conn.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO wms_app")
    owner_conn.execute("REVOKE UPDATE, DELETE, TRUNCATE ON TABLE stock_movements, audit_logs FROM wms_app")
    owner_conn.execute("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE schema_migrations FROM wms_app")

    parsed = urlparse(test_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5432
    return urlunparse(
        parsed._replace(netloc=f"wms_app:wms_app_pass@{host}:{port}")
    )


def test_ac08_immutability_stock_movements_and_audit_logs(
    db_conn: psycopg.Connection[dict[str, Any]],
    setup_test_database: str,
    staff_user: dict[str, Any],
) -> None:
    """AC-08 (Imutabilitas):
    - Given baris pada stock_movements dan audit_logs,
    - When UPDATE atau DELETE dicoba terhadap kedua tabel tersebut, termasuk lewat koneksi SQL langsung
      memakai role database aplikasi (wms_app),
    - Then operasi ditolak oleh database dan data tidak berubah.
    """
    # 1. Siapkan 1 baris di audit_logs dan 1 baris di stock_movements
    audit_row = audit_service.record(
        db_conn,
        user_id=int(staff_user["id"]),
        action="TEST_ACTION",
        entity_type="items",
        entity_id="1",
        new_values={"sku": "SKU-IMMUTABLE"},
        ip_address="127.0.0.1",
    )
    wh = factories.create_warehouse(db_conn, code="WH-IMM", name="Gudang Imutabel")
    loc = db_conn.execute(
        """
        INSERT INTO storage_locations (warehouse_id, code, name, is_active)
        VALUES (%s, 'A-01', 'Rak A1', TRUE)
        RETURNING id
        """,
        (wh["id"],),
    ).fetchone()
    assert loc is not None
    cat = db_conn.execute(
        "INSERT INTO categories (name, is_active) VALUES ('Kategori Uji', TRUE) RETURNING id"
    ).fetchone()
    assert cat is not None
    uom = db_conn.execute(
        "INSERT INTO uoms (code, name, allow_decimal, is_active) VALUES ('PCS', 'Pieces', FALSE, TRUE) RETURNING id"
    ).fetchone()
    assert uom is not None
    item = db_conn.execute(
        """
        INSERT INTO items (sku, name, category_id, uom_id, is_active)
        VALUES ('SKU-001', 'Barang Uji', %s, %s, TRUE)
        RETURNING id
        """,
        (cat["id"], uom["id"]),
    ).fetchone()
    assert item is not None

    mv_row = db_conn.execute(
        """
        INSERT INTO stock_movements (
            movement_type, warehouse_id, location_id, item_id,
            qty_before, qty_change, qty_after,
            reference_type, reference_id, created_by
        )
        VALUES (
            'IN_PURCHASE', %s, %s, %s,
            0.0000, 10.0000, 10.0000,
            'GOODS_RECEIPT', 1, %s
        )
        RETURNING id, qty_change, qty_after
        """,
        (wh["id"], loc["id"], item["id"], staff_user["id"]),
    ).fetchone()
    assert mv_row is not None

    # 2. Coba UPDATE dan DELETE menggunakan koneksi role aplikasi (wms_app)
    app_role_url = _ensure_wms_app_role_and_get_url(db_conn, setup_test_database)
    with psycopg.connect(app_role_url, autocommit=True, row_factory=dict_row) as app_conn:
        with pytest.raises(psycopg.Error):
            app_conn.execute(
                "UPDATE stock_movements SET qty_change = 99.0000, qty_after = 99.0000 WHERE id = %s",
                (mv_row["id"],),
            )
        with pytest.raises(psycopg.Error):
            app_conn.execute(
                "DELETE FROM stock_movements WHERE id = %s",
                (mv_row["id"],),
            )
        with pytest.raises(psycopg.Error):
            app_conn.execute(
                "UPDATE audit_logs SET action = 'TAMPERED' WHERE id = %s",
                (audit_row["id"],),
            )
        with pytest.raises(psycopg.Error):
            app_conn.execute(
                "DELETE FROM audit_logs WHERE id = %s",
                (audit_row["id"],),
            )

    # 3. Coba UPDATE dan DELETE menggunakan koneksi pemilik tabel -> tetap ditolak oleh trigger!
    with pytest.raises(psycopg.Error):
        db_conn.execute(
            "UPDATE stock_movements SET qty_change = 99.0000, qty_after = 99.0000 WHERE id = %s",
            (mv_row["id"],),
        )
    with pytest.raises(psycopg.Error):
        db_conn.execute(
            "DELETE FROM stock_movements WHERE id = %s",
            (mv_row["id"],),
        )
    with pytest.raises(psycopg.Error):
        db_conn.execute(
            "UPDATE audit_logs SET action = 'TAMPERED' WHERE id = %s",
            (audit_row["id"],),
        )
    with pytest.raises(psycopg.Error):
        db_conn.execute(
            "DELETE FROM audit_logs WHERE id = %s",
            (audit_row["id"],),
        )

    # 4. Pastikan data asli pada kedua tabel sama sekali tidak berubah
    mv_after = db_conn.execute(
        "SELECT qty_change, qty_after FROM stock_movements WHERE id = %s",
        (mv_row["id"],),
    ).fetchone()
    assert mv_after is not None
    assert mv_after["qty_change"] == Decimal("10.0000")
    assert mv_after["qty_after"] == Decimal("10.0000")

    audit_after = db_conn.execute(
        "SELECT action, new_values FROM audit_logs WHERE id = %s",
        (audit_row["id"],),
    ).fetchone()
    assert audit_after is not None
    assert audit_after["action"] == "TEST_ACTION"
    assert audit_after["new_values"] == {"sku": "SKU-IMMUTABLE"}

