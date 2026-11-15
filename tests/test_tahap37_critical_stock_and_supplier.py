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
    factories.create_item(db_conn, sku="SKU-CRIT-3", name="Item Tanpa Saldo", category_id=cat["id"], uom_id=uom["id"])

    db_conn.execute("UPDATE items SET min_stock = 10 WHERE id = %s", (item1["id"],))
    db_conn.execute("UPDATE items SET min_stock = 5 WHERE id = %s", (item2["id"],))

    # WH-A: item1 = 8 (<= 10, kritis), item2 = 20 (> 5, aman)
    # WH-B: item1 = 50 (> 10, aman), item2 = 3 (<= 5, kritis)
    # Item3: 0 stok di mana-mana (min_stock=0, kritis di view global)
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

    # 1. Global superadmin summary
    res_global = client.get("/api/v1/dashboard/summary", headers=superadmin_user["auth_headers"])
    assert res_global.status_code == 200
    g_stock = res_global.json()["stock_summary"]
    assert g_stock["total_active_items"] == 3
    # Item1 global=58 (>10), Item2 global=23 (>5), Item3 global=0 (<=0) => 1
    assert g_stock["low_stock_items_count"] == 1

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

    # 4. /stock/by-warehouse?warehouse_id=wh_a&critical_only=true -> hanya item1
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

    # 5. /stock/summary?critical_only=true -> hanya item3 (total global 0 <= 0)
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
