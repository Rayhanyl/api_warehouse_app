"""Pengujian Tahap 37: min_stock barang, dashboard critical stock scoping, filter stok kritis, dan profil pemasok lengkap."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection

from app.repositories import permission_repo
from tests import factories


def test_tahap37_item_min_stock_validation_and_crud(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
) -> None:
    cat = factories.create_category(db_conn, name="Kategori Tahap 37")
    uom = factories.create_uom(db_conn, code="PCS37", name="Pieces 37")

    # Tolak min_stock negatif
    res_bad = client.post(
        "/api/v1/items",
        headers=superadmin_user["auth_headers"],
        json={
            "sku": "SKU-MIN-BAD",
            "name": "Item Negatif",
            "category_id": cat["id"],
            "uom_id": uom["id"],
            "min_stock": "-5",
        },
    )
    assert res_bad.status_code == 422

    # Create dengan min_stock valid
    res_create = client.post(
        "/api/v1/items",
        headers=superadmin_user["auth_headers"],
        json={
            "sku": "SKU-MIN-01",
            "name": "Item Minimum Stok",
            "category_id": cat["id"],
            "uom_id": uom["id"],
            "min_stock": "12.5000",
        },
    )
    assert res_create.status_code == 201
    created = res_create.json()
    assert Decimal(created["min_stock"]) == Decimal("12.5000")

    # Patch min_stock
    res_patch = client.patch(
        f"/api/v1/items/{created['id']}",
        headers=superadmin_user["auth_headers"],
        json={"min_stock": "20"},
    )
    assert res_patch.status_code == 200
    assert Decimal(res_patch.json()["min_stock"]) == Decimal("20.0000")


def test_tahap37_dashboard_and_stock_critical_scoping(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    manager_user: dict[str, Any],
) -> None:
    cat = factories.create_category(db_conn, name="Kat Kritis")
    uom = factories.create_uom(db_conn, code="UNIT37", name="Unit 37")

    wh_a = factories.create_warehouse(db_conn, code="WH37A", name="Gudang Alpha")
    wh_b = factories.create_warehouse(db_conn, code="WH37B", name="Gudang Beta")
    loc_a = factories.create_location(db_conn, warehouse_id=wh_a["id"], code="RA1", name="Rak Alpha 1")
    loc_b = factories.create_location(db_conn, warehouse_id=wh_b["id"], code="RB1", name="Rak Beta 1")

    item1 = factories.create_item(db_conn, sku="SKU-CRIT-1", name="Item Kritis WH-A", category_id=cat["id"], uom_id=uom["id"])
    item2 = factories.create_item(db_conn, sku="SKU-CRIT-2", name="Item Kritis WH-B", category_id=cat["id"], uom_id=uom["id"])
    item3 = factories.create_item(db_conn, sku="SKU-CRIT-3", name="Item Tanpa Saldo", category_id=cat["id"], uom_id=uom["id"])

    db_conn.execute("UPDATE items SET min_stock = 10 WHERE id = %s", (item1["id"],))
    db_conn.execute("UPDATE items SET min_stock = 5 WHERE id = %s", (item2["id"],))

    # WH-A: item1 = 8 (<= 10, kritis), item2 = 20 (> 5, aman)
    # WH-B: item1 = 50 (> 10, aman), item2 = 3 (<= 5, kritis)
    # Item3: 0 stok di mana-mana dengan min_stock=0 (bukan kritis karena min_stock=0)
    db_conn.execute(
        """
        INSERT INTO inventory_balances (warehouse_id, location_id, item_id, qty_on_hand, created_by)
        VALUES
          (%s, %s, %s, 8, %s),
          (%s, %s, %s, 20, %s),
          (%s, %s, %s, 50, %s),
          (%s, %s, %s, 3, %s)
        """,
        (
            wh_a["id"], loc_a["id"], item1["id"], superadmin_user["id"],
            wh_a["id"], loc_a["id"], item2["id"], superadmin_user["id"],
            wh_b["id"], loc_b["id"], item1["id"], superadmin_user["id"],
            wh_b["id"], loc_b["id"], item2["id"], superadmin_user["id"],
        ),
    )

    # 1. Global superadmin summary: 2 baris kritis per gudang ((WH-A, item1) + (WH-B, item2))
    res_global = client.get("/api/v1/dashboard/summary", headers=superadmin_user["auth_headers"])
    assert res_global.status_code == 200
    g_stock = res_global.json()["stock_summary"]
    assert g_stock["total_active_items"] == 3
    assert g_stock["low_stock_items_count"] == 2

    # 2. Filter superadmin ke WH-A -> tidak bocor item2/item3 dari luar WH-A
    res_wha = client.get(
        f"/api/v1/dashboard/summary?warehouse_id={wh_a['id']}",
        headers=superadmin_user["auth_headers"],
    )
    assert res_wha.status_code == 200
    wha_stock = res_wha.json()["stock_summary"]
    assert wha_stock["total_active_items"] == 2
    assert wha_stock["low_stock_items_count"] == 1

    # 3. Manager ditugaskan ke WH-B saja
    permission_repo.update_user_warehouses(
        db_conn,
        user_id=manager_user["id"],
        warehouse_ids=[wh_b["id"]],
        actor_id=superadmin_user["id"],
    )
    res_whb = client.get("/api/v1/dashboard/summary", headers=manager_user["auth_headers"])
    assert res_whb.status_code == 200
    whb_stock = res_whb.json()["stock_summary"]
    assert whb_stock["total_active_items"] == 2
    assert whb_stock["low_stock_items_count"] == 1

    # 4. /stock/by-warehouse?critical_only=true global -> 2 baris (identik 1:1 dengan dashboard global)
    res_by_wh_all = client.get(
        "/api/v1/stock/by-warehouse?critical_only=true",
        headers=superadmin_user["auth_headers"],
    )
    assert res_by_wh_all.status_code == 200
    assert res_by_wh_all.json()["total"] == 2

    # /stock/by-warehouse?warehouse_id=wh_a&critical_only=true -> hanya item1
    res_by_wh = client.get(
        f"/api/v1/stock/by-warehouse?warehouse_id={wh_a['id']}&critical_only=true",
        headers=superadmin_user["auth_headers"],
    )
    assert res_by_wh.status_code == 200
    wh_items = res_by_wh.json()["items"]
    assert len(wh_items) == 1
    assert wh_items[0]["item_sku"] == "SKU-CRIT-1"
    assert wh_items[0]["is_critical"] is True
    assert Decimal(wh_items[0]["min_stock"]) == Decimal("10.0000")

    # 5. /stock/summary?critical_only=true -> item3 min_stock=0 tidak dianggap kritis;
    # setelah min_stock diset > 0 barulah muncul di summary kritis.
    res_summary_zero = client.get(
        "/api/v1/stock/summary?critical_only=true",
        headers=superadmin_user["auth_headers"],
    )
    assert res_summary_zero.status_code == 200
    assert res_summary_zero.json()["items"] == []

    db_conn.execute("UPDATE items SET min_stock = 5 WHERE id = %s", (item3["id"],))
    res_summary = client.get(
        "/api/v1/stock/summary?critical_only=true",
        headers=superadmin_user["auth_headers"],
    )
    assert res_summary.status_code == 200
    sum_items = res_summary.json()["items"]
    assert [row["item_sku"] for row in sum_items] == ["SKU-CRIT-3"]
    assert sum_items[0]["is_critical"] is True


def test_tahap37_supplier_enrichment_and_po_propagation(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
) -> None:
    cat = factories.create_category(db_conn, name="Kat Supplier PO")
    uom = factories.create_uom(db_conn, code="BOX37", name="Box 37")
    wh = factories.create_warehouse(db_conn, code="WH37S", name="Gudang Supplier Test")
    item = factories.create_item(db_conn, sku="SKU-SUP-37", name="Item PO Supplier", category_id=cat["id"], uom_id=uom["id"])

    res_sup = client.post(
        "/api/v1/suppliers",
        headers=superadmin_user["auth_headers"],
        json={
            "code": "SUP-37",
            "name": "PT Pemasok Lengkap",
            "contact_person": "Budi Santoso",
            "phone": "021-5550101",
            "fax": "021-5550102",
            "email": "budi@pemasok.test",
            "address": "Jl. Industri No. 9",
            "bank_name": "BCA",
            "bank_account_number": "1234567890",
            "bank_account_holder": "PT Pemasok Lengkap",
            "npwp": "01.234.567.8-901.000",
            "payment_terms": "NET 30",
            "notes": "Kirim sebelum jam 15:00",
        },
    )
    assert res_sup.status_code == 201
    sup = res_sup.json()
    assert sup["fax"] == "021-5550102"
    assert sup["bank_name"] == "BCA"
    assert sup["bank_account_number"] == "1234567890"
    assert sup["bank_account_holder"] == "PT Pemasok Lengkap"
    assert sup["npwp"] == "01.234.567.8-901.000"
    assert sup["payment_terms"] == "NET 30"

    # Update sebagian detail rekening
    res_patch = client.patch(
        f"/api/v1/suppliers/{sup['id']}",
        headers=superadmin_user["auth_headers"],
        json={"payment_terms": "NET 45", "bank_name": "Bank Mandiri"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["payment_terms"] == "NET 45"
    assert res_patch.json()["bank_name"] == "Bank Mandiri"

    # Buat PO dan cek detail supplier pada GET /purchase-orders/{id}
    res_po = client.post(
        "/api/v1/purchase-orders",
        headers=superadmin_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh["id"],
            "order_date": "2026-11-15",
            "lines": [{"item_id": item["id"], "qty_ordered": "10"}],
        },
    )
    assert res_po.status_code == 201
    po_id = res_po.json()["id"]

    res_po_detail = client.get(
        f"/api/v1/purchase-orders/{po_id}",
        headers=superadmin_user["auth_headers"],
    )
    assert res_po_detail.status_code == 200
    po = res_po_detail.json()
    assert po["supplier_fax"] == "021-5550102"
    assert po["supplier_bank_name"] == "Bank Mandiri"
    assert po["supplier_bank_account_number"] == "1234567890"
    assert po["supplier_bank_account_holder"] == "PT Pemasok Lengkap"
    assert po["supplier_npwp"] == "01.234.567.8-901.000"
    assert po["supplier_payment_terms"] == "NET 45"


def test_tahap39_dashboard_accuracy_across_warehouses_and_multi_warehouse_scope(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    manager_user: dict[str, Any],
) -> None:
    """Tahap 39:
    - low_stock_items_count 1:1 dengan /stock/by-warehouse?critical_only=true termasuk item yang baru in-transit (`qty_on_hand = 0`, `min_stock > 0`).
    - Item dengan min_stock = 0 tidak dianggap kritis meskipun saldo 0.
    - Penjumlahan metrik tiap gudang aktif sama persis dengan agregat 'Semua gudang' (mengabaikan gudang/item nonaktif).
    - Manager multi-gudang menerima agregat gabungan gudang yang ditugaskan saat tanpa `?warehouse_id`.
    """
    cat = factories.create_category(db_conn, name="Kat Tahap 39")
    uom = factories.create_uom(db_conn, code="PCS39", name="Pieces 39")
    supplier = factories.create_supplier(db_conn, code="SUP-39", name="Supplier 39")

    wh_a = factories.create_warehouse(db_conn, code="WH39A", name="Gudang 39A")
    wh_b = factories.create_warehouse(db_conn, code="WH39B", name="Gudang 39B")
    wh_c = factories.create_warehouse(db_conn, code="WH39C", name="Gudang 39C")
    wh_inactive = factories.create_warehouse(db_conn, code="WH39OFF", name="Gudang Nonaktif")
    db_conn.execute("UPDATE warehouses SET is_active = FALSE WHERE id = %s", (wh_inactive["id"],))

    loc_a = factories.create_location(db_conn, warehouse_id=wh_a["id"], code="R39A", name="Rak 39A")
    loc_b = factories.create_location(db_conn, warehouse_id=wh_b["id"], code="R39B", name="Rak 39B")
    loc_c = factories.create_location(db_conn, warehouse_id=wh_c["id"], code="R39C", name="Rak 39C")
    loc_off = factories.create_location(db_conn, warehouse_id=wh_inactive["id"], code="R39OFF", name="Rak Nonaktif")

    # item_transit: stok on_hand=0 di WH-B tetapi ada SHIPPED in-transit ke WH-B dan min_stock=10 -> kritis di WH-B!
    item_transit = factories.create_item(db_conn, sku="SKU-39-TR", name="Item Transit Kritis", category_id=cat["id"], uom_id=uom["id"])
    db_conn.execute("UPDATE items SET min_stock = 10 WHERE id = %s", (item_transit["id"],))

    # item_zero_min: min_stock=0 dan qty_on_hand=0 -> tidak boleh masuk hitungan kritis
    item_zero_min = factories.create_item(db_conn, sku="SKU-39-ZMIN", name="Item Min Nol", category_id=cat["id"], uom_id=uom["id"])

    # item_safe: qty mencukupi
    item_safe = factories.create_item(db_conn, sku="SKU-39-OK", name="Item Aman", category_id=cat["id"], uom_id=uom["id"])
    db_conn.execute("UPDATE items SET min_stock = 5 WHERE id = %s", (item_safe["id"],))

    # Balances: WH-A (item_transit=20 > 10 aman, item_zero_min=0 tidak kritis), WH-C (item_safe=4 <= 5 kritis), WH-inactive (item_safe=1)
    db_conn.execute(
        """
        INSERT INTO inventory_balances (warehouse_id, location_id, item_id, qty_on_hand, created_by)
        VALUES
          (%s, %s, %s, 20, %s),
          (%s, %s, %s, 0, %s),
          (%s, %s, %s, 4, %s),
          (%s, %s, %s, 1, %s)
        """,
        (
            wh_a["id"], loc_a["id"], item_transit["id"], superadmin_user["id"],
            wh_a["id"], loc_a["id"], item_zero_min["id"], superadmin_user["id"],
            wh_c["id"], loc_c["id"], item_safe["id"], superadmin_user["id"],
            wh_inactive["id"], loc_off["id"], item_safe["id"], superadmin_user["id"],
        ),
    )

    # Transfer SHIPPED dari WH-A ke WH-B untuk item_transit qty=8 -> WH-B punya in_transit=8, on_hand=0 (<= 10)
    trf_row = db_conn.execute(
        """
        INSERT INTO stock_transfers (
            transfer_number, source_warehouse_id, source_location_id,
            destination_warehouse_id, destination_location_id,
            status, created_by, approved_by, approved_at, shipped_by, shipped_at
        )
        VALUES (
            'TR-39-0001', %s, %s, %s, %s, 'SHIPPED',
            %s, %s, CURRENT_TIMESTAMP, %s, CURRENT_TIMESTAMP
        )
        RETURNING id
        """,
        (
            wh_a["id"], loc_a["id"], wh_b["id"], loc_b["id"],
            superadmin_user["id"], superadmin_user["id"], superadmin_user["id"],
        ),
    ).fetchone()
    assert trf_row is not None
    db_conn.execute(
        "INSERT INTO stock_transfer_lines (transfer_id, item_id, qty, created_by) VALUES (%s, %s, 8, %s)",
        (trf_row["id"], item_transit["id"], superadmin_user["id"]),
    )

    # PO ISSUED pada gudang aktif (WH-A) dan gudang nonaktif (harus diabaikan oleh global summary)
    db_conn.execute(
        """
        INSERT INTO purchase_orders (po_number, supplier_id, warehouse_id, status, order_date, created_by, issued_by, issued_at)
        VALUES
          ('PO-39-ACT', %s, %s, 'ISSUED', CURRENT_DATE, %s, %s, CURRENT_TIMESTAMP),
          ('PO-39-OFF', %s, %s, 'ISSUED', CURRENT_DATE, %s, %s, CURRENT_TIMESTAMP)
        """,
        (
            supplier["id"], wh_a["id"], superadmin_user["id"], superadmin_user["id"],
            supplier["id"], wh_inactive["id"], superadmin_user["id"], superadmin_user["id"],
        ),
    )

    # 1. Verifikasi kesamaan Global Dashboard vs penjumlahan seluruh gudang aktif
    global_data = client.get("/api/v1/dashboard/summary", headers=superadmin_user["auth_headers"]).json()
    global_crit_list = client.get(
        "/api/v1/stock/by-warehouse?critical_only=true&limit=200",
        headers=superadmin_user["auth_headers"],
    ).json()
    assert global_data["stock_summary"]["low_stock_items_count"] == global_crit_list["total"] == 2

    sum_on_hand = Decimal("0")
    sum_in_transit = Decimal("0")
    sum_low = 0
    sum_pending_po = 0
    for wid in (wh_a["id"], wh_b["id"], wh_c["id"]):
        wh_data = client.get(
            f"/api/v1/dashboard/summary?warehouse_id={wid}",
            headers=superadmin_user["auth_headers"],
        ).json()
        wh_crit = client.get(
            f"/api/v1/stock/by-warehouse?warehouse_id={wid}&critical_only=true",
            headers=superadmin_user["auth_headers"],
        ).json()
        assert wh_data["stock_summary"]["low_stock_items_count"] == wh_crit["total"]
        sum_on_hand += Decimal(wh_data["stock_summary"]["total_qty_on_hand"])
        sum_in_transit += Decimal(wh_data["stock_summary"]["total_qty_in_transit"])
        sum_low += wh_data["stock_summary"]["low_stock_items_count"]
        sum_pending_po += wh_data["pending_actions"]["pending_po_receipt_count"]

    assert sum_on_hand == Decimal(global_data["stock_summary"]["total_qty_on_hand"]) == Decimal("24.0000")
    assert sum_in_transit == Decimal(global_data["stock_summary"]["total_qty_in_transit"]) == Decimal("8.0000")
    assert sum_low == global_data["stock_summary"]["low_stock_items_count"] == 2
    assert sum_pending_po == global_data["pending_actions"]["pending_po_receipt_count"] == 1

    # 2. Verifikasi user operasional multi-gudang ([wh_a, wh_b]) tanpa filter melihat gabungan keduanya (bukan wh_c)
    permission_repo.update_user_warehouses(
        db_conn,
        user_id=manager_user["id"],
        warehouse_ids=[wh_a["id"], wh_b["id"]],
        actor_id=superadmin_user["id"],
    )
    mgr_all = client.get("/api/v1/dashboard/summary", headers=manager_user["auth_headers"])
    assert mgr_all.status_code == 200
    mgr_json = mgr_all.json()
    assert sorted(w["id"] for w in mgr_json["assigned_warehouses"]) == sorted([wh_a["id"], wh_b["id"]])
    assert Decimal(mgr_json["stock_summary"]["total_qty_on_hand"]) == Decimal("20.0000")
    assert Decimal(mgr_json["stock_summary"]["total_qty_in_transit"]) == Decimal("8.0000")
    assert mgr_json["stock_summary"]["low_stock_items_count"] == 1  # item_transit di WH-B

    # Filter spesifik ke wh_a diperbolehkan; ke wh_c ditolak 403
    mgr_wha = client.get(
        f"/api/v1/dashboard/summary?warehouse_id={wh_a['id']}",
        headers=manager_user["auth_headers"],
    )
    assert mgr_wha.status_code == 200
    assert mgr_wha.json()["stock_summary"]["low_stock_items_count"] == 0

    mgr_whc = client.get(
        f"/api/v1/dashboard/summary?warehouse_id={wh_c['id']}",
        headers=manager_user["auth_headers"],
    )
    assert mgr_whc.status_code == 403


def test_tahap40_master_data_server_side_search_and_pagination(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
) -> None:
    """Tahap 40:
    - GET /api/v1/items?search= mencari berdasarkan SKU, nama barang, nama kategori (`c.name`), dan kode UoM (`u.code`), serta mendukung filter `category_id` + `uom_id` + paginasi server-side.
    - GET /api/v1/locations?search= mencari berdasarkan kode/nama rak maupun kode/nama gudang (`w.code`, `w.name`).
    """
    cat_khusus = factories.create_category(db_conn, name="ElektronikPresisi40")
    uom_khusus = factories.create_uom(db_conn, code="ROLL40", name="Roll Tahap 40")
    item_a = factories.create_item(
        db_conn,
        sku="SKU-40-A",
        name="Kabel Sensor",
        category_id=cat_khusus["id"],
        uom_id=uom_khusus["id"],
    )

    wh_khusus = factories.create_warehouse(db_conn, code="WH40KHS", name="Gudang Logistik Terpadu 40")
    loc_a = factories.create_location(
        db_conn,
        warehouse_id=wh_khusus["id"],
        code="RAK-40-01",
        name="Lorong Utama 40",
    )

    # Search items by category name
    res_cat_search = client.get(
        "/api/v1/items?search=ElektronikPresisi40",
        headers=superadmin_user["auth_headers"],
    )
    assert res_cat_search.status_code == 200
    body_cat = res_cat_search.json()
    assert body_cat["total"] == 1
    assert body_cat["items"][0]["id"] == item_a["id"]

    # Search items by UoM code
    res_uom_search = client.get(
        "/api/v1/items?search=ROLL40",
        headers=superadmin_user["auth_headers"],
    )
    assert res_uom_search.status_code == 200
    assert res_uom_search.json()["total"] == 1
    assert res_uom_search.json()["items"][0]["sku"] == "SKU-40-A"

    # Search locations by warehouse code & warehouse name
    res_loc_wh_code = client.get(
        "/api/v1/locations?search=WH40KHS",
        headers=superadmin_user["auth_headers"],
    )
    assert res_loc_wh_code.status_code == 200
    assert res_loc_wh_code.json()["total"] == 1
    assert res_loc_wh_code.json()["items"][0]["id"] == loc_a["id"]

    res_loc_wh_name = client.get(
        "/api/v1/locations?search=Logistik Terpadu 40",
        headers=superadmin_user["auth_headers"],
    )
    assert res_loc_wh_name.status_code == 200
    assert res_loc_wh_name.json()["total"] == 1
    assert res_loc_wh_name.json()["items"][0]["code"] == "RAK-40-01"

