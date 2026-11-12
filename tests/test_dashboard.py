"""Pengujian API Dashboard operasional (DSH-F01, AC-38) dan penegakan warehouse scoping."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection

from app.repositories import permission_repo
from tests import factories


def test_ac38_dashboard_summary_superadmin_and_scoping(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    manager_user: dict[str, Any],
) -> None:
    """AC-38:
    - Super Admin menerima ringkasan metrik global lintas seluruh gudang.
    - Warehouse Manager hanya menerima ringkasan metrik pada gudang yang ditugaskan.
    """
    # 1. Setup Data Master: Kategori, UoM, 2 Gudang, 2 Lokasi, 3 Item
    cat = factories.create_category(db_conn, name="Elektronik Dashboard")
    uom = factories.create_uom(db_conn, code="PCS", name="Pieces")

    item1 = factories.create_item(
        db_conn, sku="SKU-DSH-001", name="Laptop Gaming", category_id=cat["id"], uom_id=uom["id"]
    )
    item2 = factories.create_item(
        db_conn, sku="SKU-DSH-002", name="Mouse Wireless", category_id=cat["id"], uom_id=uom["id"]
    )
    # Item 3 tanpa stok sama sekali (low stock / zero stock)
    item3 = factories.create_item(
        db_conn, sku="SKU-DSH-003", name="Keyboard RGB", category_id=cat["id"], uom_id=uom["id"]
    )

    wh_a = factories.create_warehouse(db_conn, code="WHA", name="Gudang Barat")
    wh_b = factories.create_warehouse(db_conn, code="WHB", name="Gudang Timur")

    loc_a = factories.create_location(db_conn, warehouse_id=wh_a["id"], code="LOC-A1", name="Rak A1")
    loc_b = factories.create_location(db_conn, warehouse_id=wh_b["id"], code="LOC-B1", name="Rak B1")

    # Saldo stok:
    # Gudang A: item1 = 15.0000
    # Gudang B: item2 = 25.0000
    db_conn.execute(
        """
        INSERT INTO inventory_balances (warehouse_id, location_id, item_id, qty_on_hand, created_by)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (wh_a["id"], loc_a["id"], item1["id"], Decimal("15.0000"), superadmin_user["id"]),
    )
    db_conn.execute(
        """
        INSERT INTO inventory_balances (warehouse_id, location_id, item_id, qty_on_hand, created_by)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (wh_b["id"], loc_b["id"], item2["id"], Decimal("25.0000"), superadmin_user["id"]),
    )

    # Catat movement mutasi untuk recent activities
    db_conn.execute(
        """
        INSERT INTO stock_movements (
            movement_type, warehouse_id, location_id, item_id,
            qty_before, qty_change, qty_after,
            reference_type, reference_id, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            "IN_PURCHASE", wh_a["id"], loc_a["id"], item1["id"],
            Decimal("0.0000"), Decimal("15.0000"), Decimal("15.0000"),
            "GOODS_RECEIPT", 999, superadmin_user["id"]
        ),
    )

    # Dokumen transaksi:
    # 1 PO berstatus ISSUED pada Gudang A
    supplier = factories.create_supplier(db_conn, code="SUP-DSH", name="Supplier Prima")
    po_row = db_conn.execute(
        """
        INSERT INTO purchase_orders (
            po_number, supplier_id, warehouse_id, status, order_date, created_by,
            issued_by, issued_at
        )
        VALUES ('PO-202611-0001', %s, %s, 'ISSUED', CURRENT_DATE, %s, %s, CURRENT_TIMESTAMP)
        RETURNING id
        """,
        (supplier["id"], wh_a["id"], superadmin_user["id"], superadmin_user["id"]),
    ).fetchone()
    assert po_row is not None

    # 1 Draft GR pada Gudang A
    db_conn.execute(
        """
        INSERT INTO goods_receipts (gr_number, po_id, warehouse_id, status, received_date, created_by)
        VALUES ('GR-202611-0001', %s, %s, 'DRAFT', CURRENT_DATE, %s)
        """,
        (po_row["id"], wh_a["id"], superadmin_user["id"]),
    )

    # 1 Transfer SHIPPED dari Gudang A ke Gudang B
    trf_row = db_conn.execute(
        """
        INSERT INTO stock_transfers (
            transfer_number, source_warehouse_id, source_location_id,
            destination_warehouse_id, destination_location_id,
            status, created_by,
            approved_by, approved_at, shipped_by, shipped_at
        )
        VALUES (
            'TR-202611-0001', %s, %s, %s, %s, 'SHIPPED', %s,
            %s, CURRENT_TIMESTAMP, %s, CURRENT_TIMESTAMP
        )
        RETURNING id
        """,
        (
            wh_a["id"], loc_a["id"], wh_b["id"], loc_b["id"], superadmin_user["id"],
            superadmin_user["id"], superadmin_user["id"]
        ),
    ).fetchone()
    assert trf_row is not None

    db_conn.execute(
        """
        INSERT INTO stock_transfer_lines (transfer_id, item_id, qty, created_by)
        VALUES (%s, %s, %s, %s)
        """,
        (trf_row["id"], item1["id"], Decimal("5.0000"), superadmin_user["id"]),
    )

    # Tugaskan manager_user HANYA ke Gudang A
    permission_repo.update_user_warehouses(
        db_conn, user_id=manager_user["id"], warehouse_ids=[wh_a["id"]], actor_id=superadmin_user["id"]
    )

    # -------------------------------------------------------------------------
    # 2. Uji Super Admin (Unscoped Global View)
    # -------------------------------------------------------------------------
    sa_res = client.get("/api/v1/dashboard/summary", headers=superadmin_user["auth_headers"])
    assert sa_res.status_code == 200, sa_res.text
    sa_data = sa_res.json()

    # Periksa ringkasan stok global
    stock_sa = sa_data["stock_summary"]
    assert stock_sa["total_active_items"] >= 3
    # 15.0000 (A) + 25.0000 (B) = 40.0000
    assert Decimal(stock_sa["total_qty_on_hand"]) == Decimal("40.0000")
    # Transfer in-transit ke B = 5.0000
    assert Decimal(stock_sa["total_qty_in_transit"]) == Decimal("5.0000")
    # item3 saldo 0 -> low stock minimal 1
    assert stock_sa["low_stock_items_count"] >= 1

    # Periksa pending actions global
    actions_sa = sa_data["pending_actions"]
    assert actions_sa["pending_po_receipt_count"] >= 1
    assert actions_sa["draft_gr_count"] >= 1
    assert actions_sa["pending_transfer_receive_count"] >= 1

    # Periksa recent activities
    recent_sa = sa_data["recent_activities"]
    assert len(recent_sa) >= 1
    assert recent_sa[0]["movement_type"] == "IN_PURCHASE"
    assert recent_sa[0]["item_sku"] == "SKU-DSH-001"

    # Periksa assigned warehouses (Super Admin melihat semua gudang aktif)
    wh_ids_sa = [w["id"] for w in sa_data["assigned_warehouses"]]
    assert wh_a["id"] in wh_ids_sa
    assert wh_b["id"] in wh_ids_sa

    # -------------------------------------------------------------------------
    # 3. Uji Warehouse Manager (Scoped to Gudang A only)
    # -------------------------------------------------------------------------
    mgr_res = client.get("/api/v1/dashboard/summary", headers=manager_user["auth_headers"])
    assert mgr_res.status_code == 200, mgr_res.text
    mgr_data = mgr_res.json()

    # Periksa assigned warehouses (hanya Gudang A)
    wh_ids_mgr = [w["id"] for w in mgr_data["assigned_warehouses"]]
    assert wh_ids_mgr == [wh_a["id"]]

    # Saldo stok manager hanya pada Gudang A = 15.0000 (tidak melihat 25.0000 milik B)
    stock_mgr = mgr_data["stock_summary"]
    assert Decimal(stock_mgr["total_qty_on_hand"]) == Decimal("15.0000")
    # Transfer menuju Gudang A = 0 (karena transfer tujuan B)
    assert Decimal(stock_mgr["total_qty_in_transit"]) == Decimal("0.0000")

    # Pending actions manager:
    # PO Gudang A = 1
    # GR draft Gudang A = 1
    # Transfer receive Gudang A = 0 (karena transfer tujuan B)
    actions_mgr = mgr_data["pending_actions"]
    assert actions_mgr["pending_po_receipt_count"] == 1
    assert actions_mgr["draft_gr_count"] == 1
    assert actions_mgr["pending_transfer_receive_count"] == 0


def test_ac38_dashboard_summary_unassigned_user_and_auth(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    staff_user: dict[str, Any],
    superadmin_user: dict[str, Any],
) -> None:
    """AC-38:
    - Pengguna tanpa penugasan gudang menerima metrik stok 0 dan list kosong secara aman.
    - Akses tanpa token ditolak dengan HTTP 401.
    """
    # 1. Hapus penugasan gudang untuk staff_user
    permission_repo.update_user_warehouses(
        db_conn, user_id=staff_user["id"], warehouse_ids=[], actor_id=superadmin_user["id"]
    )

    staff_res = client.get("/api/v1/dashboard/summary", headers=staff_user["auth_headers"])
    assert staff_res.status_code == 200
    staff_data = staff_res.json()

    assert staff_data["assigned_warehouses"] == []
    assert staff_data["stock_summary"]["total_active_items"] == 0
    assert Decimal(staff_data["stock_summary"]["total_qty_on_hand"]) == Decimal("0.0000")
    assert Decimal(staff_data["stock_summary"]["total_qty_in_transit"]) == Decimal("0.0000")
    assert staff_data["stock_summary"]["low_stock_items_count"] == 0
    assert staff_data["pending_actions"]["pending_po_receipt_count"] == 0
    assert staff_data["recent_activities"] == []

    # 2. Tanpa autentikasi -> 401
    unauth_res = client.get("/api/v1/dashboard/summary")
    assert unauth_res.status_code == 401
