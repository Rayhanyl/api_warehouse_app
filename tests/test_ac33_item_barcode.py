"""Pengujian terfokus untuk Kriteria Penerimaan AC-33: Manajemen Barcode Barang & Lookup Scanner (MST-F08, INV-F07)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection

from tests import factories


def test_ac33_item_barcode_crud_uniqueness_and_lookup(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
) -> None:
    """AC-33:
    - Buat barang dengan barcode opsional & validasi keunikan case-insensitive (409 DUPLICATE_VALUE).
    - Pembaruan dan pengosongan barcode pada PATCH /api/v1/items/{id}.
    - Pencarian barang dengan parameter ?barcode= (exact match barcode/SKU) dan ?search= (ILIKE barcode).
    """
    headers = superadmin_user["auth_headers"]
    cat = factories.create_category(db_conn, name="Retail Cat")
    uom = factories.create_uom(db_conn, code="PCS-BC", name="Pieces Barcode", allow_decimal=False)

    # 1. Buat barang dengan barcode EAN-13
    res1 = client.post(
        "/api/v1/items",
        headers=headers,
        json={
            "sku": "SKU-BC-001",
            "barcode": "8991234567890",
            "name": "Minuman Botol 500ml",
            "category_id": cat["id"],
            "uom_id": uom["id"],
        },
    )
    assert res1.status_code == 201, res1.text
    item1 = res1.json()
    assert item1["sku"] == "SKU-BC-001"
    assert item1["barcode"] == "8991234567890"

    # 2. Buat barang kedua tanpa barcode (opsional / null)
    res2 = client.post(
        "/api/v1/items",
        headers=headers,
        json={
            "sku": "SKU-BC-002",
            "barcode": "   ",
            "name": "Snack Keripik",
            "category_id": cat["id"],
            "uom_id": uom["id"],
        },
    )
    assert res2.status_code == 201, res2.text
    item2 = res2.json()
    assert item2["barcode"] is None

    # 3. Duplikasi barcode ditolak 409 DUPLICATE
    res_dup = client.post(
        "/api/v1/items",
        headers=headers,
        json={
            "sku": "SKU-BC-003",
            "barcode": "8991234567890",
            "name": "Barang Duplikat Barcode",
            "category_id": cat["id"],
            "uom_id": uom["id"],
        },
    )
    assert res_dup.status_code == 409
    assert res_dup.json()["error"]["code"] == "DUPLICATE"
    assert res_dup.json()["error"]["details"]["field"] == "barcode"

    # 4. Update item2 untuk menambahkan barcode alfanumerik (Code-128), lalu uji duplikasi case-insensitive
    res_upd = client.patch(
        f"/api/v1/items/{item2['id']}",
        headers=headers,
        json={"barcode": "BC-ALPHA-99"},
    )
    assert res_upd.status_code == 200
    assert res_upd.json()["barcode"] == "BC-ALPHA-99"

    res_dup_patch = client.patch(
        f"/api/v1/items/{item1['id']}",
        headers=headers,
        json={"barcode": "bc-alpha-99"},
    )
    assert res_dup_patch.status_code == 409
    assert res_dup_patch.json()["error"]["code"] == "DUPLICATE"

    # 5. Lookup menggunakan ?barcode=8991234567890 maupun ?barcode=SKU-BC-002
    res_lookup_bc = client.get(
        "/api/v1/items?barcode=8991234567890",
        headers=headers,
    )
    assert res_lookup_bc.status_code == 200
    assert res_lookup_bc.json()["total"] == 1
    assert res_lookup_bc.json()["items"][0]["id"] == item1["id"]

    res_lookup_sku = client.get(
        "/api/v1/items?barcode=sku-bc-002",
        headers=headers,
    )
    assert res_lookup_sku.status_code == 200
    assert res_lookup_sku.json()["total"] == 1
    assert res_lookup_sku.json()["items"][0]["id"] == item2["id"]

    # 6. Pencarian umum ?search=456789 mencocokkan kolom barcode
    res_search = client.get(
        "/api/v1/items?search=456789",
        headers=headers,
    )
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 1
    assert res_search.json()["items"][0]["id"] == item1["id"]

    # 7. Kosongkan barcode kembali menjadi None melalui PATCH
    res_clear = client.patch(
        f"/api/v1/items/{item2['id']}",
        headers=headers,
        json={"barcode": None},
    )
    assert res_clear.status_code == 200
    assert res_clear.json()["barcode"] is None


def test_ac32_ac33_transaction_lines_and_stock_include_item_barcode(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
) -> None:
    """Memastikan item_barcode disertakan pada PO Lines, GR Lines, Transfer Lines, dan Saldo Stok."""
    headers = superadmin_user["auth_headers"]
    cat = factories.create_category(db_conn, name="B2B Cat")
    uom = factories.create_uom(db_conn, code="BOX", name="Box", allow_decimal=False)
    sup = factories.create_supplier(db_conn, code="SUP-BC", name="PT Pemasok Barcode")
    wh_src = factories.create_warehouse(db_conn, code="WH-PUSAT", name="Gudang Pusat")
    loc_src = factories.create_location(db_conn, warehouse_id=wh_src["id"], code="R-01", name="Rak 01")
    wh_dst = factories.create_warehouse(db_conn, code="WH-CABANG", name="Toko Cabang A")
    loc_dst = factories.create_location(db_conn, warehouse_id=wh_dst["id"], code="D-01", name="Display 01")

    res_item = client.post(
        "/api/v1/items",
        headers=headers,
        json={
            "sku": "SKU-B2B-01",
            "barcode": "8990001112223",
            "name": "Karton Susu UHT",
            "category_id": cat["id"],
            "uom_id": uom["id"],
        },
    )
    assert res_item.status_code == 201
    item = res_item.json()

    # Buat & Issue PO
    res_po = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh_src["id"],
            "order_date": str(date.today()),
            "lines": [{"item_id": item["id"], "qty_ordered": "10"}],
        },
    )
    assert res_po.status_code == 201
    po = res_po.json()
    assert po["lines"][0]["item_barcode"] == "8990001112223"
    po_line_id = po["lines"][0]["id"]

    client.post(f"/api/v1/purchase-orders/{po['id']}/issue", headers=headers)

    # Buat & Post GR
    res_gr = client.post(
        "/api/v1/goods-receipts",
        headers=headers,
        json={
            "po_id": po["id"],
            "received_date": str(date.today()),
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "location_id": loc_src["id"],
                    "qty_received": "10",
                }
            ],
        },
    )
    assert res_gr.status_code == 201
    gr = res_gr.json()
    assert gr["lines"][0]["item_barcode"] == "8990001112223"
    client.post(f"/api/v1/goods-receipts/{gr['id']}/post", headers=headers)

    # Cek pencarian barcode pada halaman Stok
    res_stock = client.get(
        "/api/v1/stock/by-location?search=8990001112223",
        headers=headers,
    )
    assert res_stock.status_code == 200
    assert res_stock.json()["total"] == 1
    assert res_stock.json()["items"][0]["item_barcode"] == "8990001112223"

    # AC-36: Cek pencarian kode Lokasi Rak (R-01) dan Kode Gudang (WH-PUSAT) pada /stock/by-location
    res_rack = client.get(
        "/api/v1/stock/by-location?search=R-01",
        headers=headers,
    )
    assert res_rack.status_code == 200
    assert res_rack.json()["total"] == 1
    assert res_rack.json()["items"][0]["location_code"] == "R-01"

    res_wh = client.get(
        "/api/v1/stock/by-location?search=WH-PUSAT",
        headers=headers,
    )
    assert res_wh.status_code == 200
    assert res_wh.json()["total"] == 1
    assert res_wh.json()["items"][0]["warehouse_code"] == "WH-PUSAT"

    # Buat Stock Transfer
    res_trf = client.post(
        "/api/v1/stock-transfers",
        headers=headers,
        json={
            "source_warehouse_id": wh_src["id"],
            "source_location_id": loc_src["id"],
            "destination_warehouse_id": wh_dst["id"],
            "destination_location_id": loc_dst["id"],
            "lines": [{"item_id": item["id"], "qty": "4"}],
        },
    )
    assert res_trf.status_code == 201
    trf = res_trf.json()
    assert trf["lines"][0]["item_barcode"] == "8990001112223"
