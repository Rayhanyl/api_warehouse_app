"""Pengujian Tahap 36: Edit PO Draft, Revise-as-Draft, Expected Delivery Date Overdue, & Line Short-Close."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection

from tests import factories


def _setup_po_context(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> dict[str, Any]:
    wh = factories.create_warehouse(db_conn, code="WH-T36", name="Gudang Tahap 36")
    loc = factories.create_location(db_conn, warehouse_id=wh["id"], code="RAK-36", name="Rak T36")
    sup = factories.create_supplier(db_conn, code="SUP-36", name="PT Pemasok 36")
    cat = factories.create_category(db_conn, name="Kat 36")
    uom = factories.create_uom(db_conn, code="PCS36", name="Pieces 36", allow_decimal=False)
    item1 = factories.create_item(
        db_conn, sku="SKU-36-1", name="Barang 36 Satu", category_id=cat["id"], uom_id=uom["id"]
    )
    item2 = factories.create_item(
        db_conn, sku="SKU-36-2", name="Barang 36 Dua", category_id=cat["id"], uom_id=uom["id"]
    )
    item3 = factories.create_item(
        db_conn, sku="SKU-36-3", name="Barang 36 Tiga", category_id=cat["id"], uom_id=uom["id"]
    )

    for user in (purchasing_user, manager_user, staff_user):
        res = client.put(
            f"/api/v1/users/{user['id']}/warehouses",
            headers=superadmin_user["auth_headers"],
            json={"warehouse_ids": [wh["id"]]},
        )
        assert res.status_code == 200

    return {
        "wh": wh,
        "loc": loc,
        "sup": sup,
        "item1": item1,
        "item2": item2,
        "item3": item3,
    }


def test_po_expected_delivery_date_validation_overdue_filter_and_draft_edit(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    ctx = _setup_po_context(client, db_conn, superadmin_user, purchasing_user, manager_user, staff_user)
    today = date.today()
    past_order = (today - timedelta(days=5)).isoformat()
    past_eta = (today - timedelta(days=2)).isoformat()
    invalid_eta = (today - timedelta(days=6)).isoformat()
    future_eta = (today + timedelta(days=5)).isoformat()

    # 1. expected_delivery_date < order_date ditolak 422
    bad_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": ctx["sup"]["id"],
            "warehouse_id": ctx["wh"]["id"],
            "order_date": past_order,
            "expected_delivery_date": invalid_eta,
            "lines": [{"item_id": ctx["item1"]["id"], "qty_ordered": "10"}],
        },
    )
    assert bad_res.status_code == 422
    assert bad_res.json()["error"]["code"] == "VALIDATION_ERROR"

    # 2. Buat PO DRAFT dengan ETA masa lalu -> edit DRAFT -> issue -> terdeteksi overdue
    draft_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": ctx["sup"]["id"],
            "warehouse_id": ctx["wh"]["id"],
            "order_date": past_order,
            "expected_delivery_date": future_eta,
            "notes": "Draft awal",
            "lines": [{"item_id": ctx["item1"]["id"], "qty_ordered": "10"}],
        },
    )
    assert draft_res.status_code == 201
    po_id = draft_res.json()["id"]
    assert draft_res.json()["is_overdue"] is False

    patch_res = client.patch(
        f"/api/v1/purchase-orders/{po_id}",
        headers=purchasing_user["auth_headers"],
        json={
            "expected_delivery_date": past_eta,
            "notes": "Draft diperbarui",
            "lines": [
                {"item_id": ctx["item1"]["id"], "qty_ordered": "12"},
                {"item_id": ctx["item2"]["id"], "qty_ordered": "5"},
            ],
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["expected_delivery_date"] == past_eta
    assert len(patch_res.json()["lines"]) == 2
    # DRAFT belum dianggap overdue operasional sampai ISSUED
    assert patch_res.json()["is_overdue"] is False

    issue_res = client.post(
        f"/api/v1/purchase-orders/{po_id}/issue",
        headers=purchasing_user["auth_headers"],
    )
    assert issue_res.status_code == 200
    assert issue_res.json()["is_overdue"] is True
    assert issue_res.json()["days_overdue"] == 2

    # 3. Buat PO kedua yang tidak overdue lalu verifikasi filter overdue_only=true
    ontime_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": ctx["sup"]["id"],
            "warehouse_id": ctx["wh"]["id"],
            "order_date": today.isoformat(),
            "expected_delivery_date": future_eta,
            "lines": [{"item_id": ctx["item3"]["id"], "qty_ordered": "3"}],
        },
    )
    assert ontime_res.status_code == 201
    client.post(
        f"/api/v1/purchase-orders/{ontime_res.json()['id']}/issue",
        headers=purchasing_user["auth_headers"],
    )

    overdue_list = client.get(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        params={"overdue_only": "true"},
    )
    assert overdue_list.status_code == 200
    po_ids = [item["id"] for item in overdue_list.json()["items"]]
    assert po_id in po_ids
    assert ontime_res.json()["id"] not in po_ids


def test_po_issued_revise_as_draft_and_block_when_gr_exists(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    ctx = _setup_po_context(client, db_conn, superadmin_user, purchasing_user, manager_user, staff_user)
    today = date.today().isoformat()

    po1_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": ctx["sup"]["id"],
            "warehouse_id": ctx["wh"]["id"],
            "order_date": today,
            "expected_delivery_date": today,
            "notes": "Pesanan asli",
            "lines": [
                {"item_id": ctx["item1"]["id"], "qty_ordered": "10", "notes": "baris 1"},
                {"item_id": ctx["item2"]["id"], "qty_ordered": "6"},
            ],
        },
    )
    assert po1_res.status_code == 201
    po1_id = po1_res.json()["id"]
    po1_num = po1_res.json()["po_number"]

    assert (
        client.post(
            f"/api/v1/purchase-orders/{po1_id}/issue",
            headers=purchasing_user["auth_headers"],
        ).status_code
        == 200
    )

    # 1. Revise-as-draft berhasil saat belum ada GR
    revise_res = client.post(
        f"/api/v1/purchase-orders/{po1_id}/revise-draft",
        headers=purchasing_user["auth_headers"],
    )
    assert revise_res.status_code == 201
    draft_po = revise_res.json()
    assert draft_po["id"] != po1_id
    assert draft_po["status"] == "DRAFT"
    assert draft_po["revised_from_po_id"] == po1_id
    assert draft_po["revised_from_po_number"] == po1_num
    assert len(draft_po["lines"]) == 2

    old_po = client.get(
        f"/api/v1/purchase-orders/{po1_id}",
        headers=purchasing_user["auth_headers"],
    )
    assert old_po.status_code == 200
    assert old_po.json()["status"] == "CANCELLED"

    # 2. Terbitkan draft hasil revisi lalu buat GR DRAFT -> revise-draft berikutnya harus ditolak 409
    po2_id = draft_po["id"]
    po2_line1_id = draft_po["lines"][0]["id"]
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po2_id}/issue",
            headers=purchasing_user["auth_headers"],
        ).status_code
        == 200
    )
    gr_res = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po2_id,
            "received_date": today,
            "lines": [
                {
                    "po_line_id": po2_line1_id,
                    "location_id": ctx["loc"]["id"],
                    "qty_received": "2",
                }
            ],
        },
    )
    assert gr_res.status_code == 201

    blocked_res = client.post(
        f"/api/v1/purchase-orders/{po2_id}/revise-draft",
        headers=purchasing_user["auth_headers"],
    )
    assert blocked_res.status_code == 409
    assert blocked_res.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_po_line_level_short_close_partial_delivery_and_auto_close_header(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    ctx = _setup_po_context(client, db_conn, superadmin_user, purchasing_user, manager_user, staff_user)
    today = date.today().isoformat()

    po_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": ctx["sup"]["id"],
            "warehouse_id": ctx["wh"]["id"],
            "order_date": today,
            "lines": [
                {"item_id": ctx["item1"]["id"], "qty_ordered": "10"},
                {"item_id": ctx["item2"]["id"], "qty_ordered": "5"},
                {"item_id": ctx["item3"]["id"], "qty_ordered": "4"},
            ],
        },
    )
    assert po_res.status_code == 201
    po_id = po_res.json()["id"]
    lines_by_item = {line["item_id"]: line for line in po_res.json()["lines"]}
    l1_id = lines_by_item[ctx["item1"]["id"]]["id"]
    l2_id = lines_by_item[ctx["item2"]["id"]]["id"]
    l3_id = lines_by_item[ctx["item3"]["id"]]["id"]

    issue_line_test = client.post(
        f"/api/v1/purchase-orders/{po_id}/issue",
        headers=purchasing_user["auth_headers"],
    )
    assert issue_line_test.status_code == 200

    # Terima sebagian barang 1 (6 dari 10)
    gr1 = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po_id,
            "received_date": today,
            "lines": [
                {"po_line_id": l1_id, "location_id": ctx["loc"]["id"], "qty_received": "6"},
            ],
        },
    )
    assert gr1.status_code == 201
    assert (
        client.post(
            f"/api/v1/goods-receipts/{gr1.json()['id']}/post",
            headers=staff_user["auth_headers"],
        ).status_code
        == 200
    )

    # Tutup sisa barang 1 (4 unit) dan hentikan penuh barang 2 (5 unit, stok supplier kosong)
    c1 = client.post(
        f"/api/v1/purchase-orders/{po_id}/lines/{l1_id}/close",
        headers=purchasing_user["auth_headers"],
        json={"closed_reason": "Sisa 4 pcs tidak dikirim supplier"},
    )
    assert c1.status_code == 200
    assert c1.json()["status"] == "PARTIALLY_RECEIVED"
    l1_after = next(line for line in c1.json()["lines"] if line["id"] == l1_id)
    assert float(l1_after["qty_closed"]) == 4.0
    assert float(l1_after["qty_remaining"]) == 0.0
    assert l1_after["line_status"] == "CLOSED"

    c2 = client.post(
        f"/api/v1/purchase-orders/{po_id}/lines/{l2_id}/close",
        headers=purchasing_user["auth_headers"],
        json={"closed_reason": "Barang 2 discontinued"},
    )
    assert c2.status_code == 200
    assert c2.json()["status"] == "PARTIALLY_RECEIVED"

    # Mencoba membuat GR untuk baris 1 yang sudah short-closed harus ditolak 409 OVER_RECEIPT
    over_gr = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po_id,
            "received_date": today,
            "lines": [
                {"po_line_id": l1_id, "location_id": ctx["loc"]["id"], "qty_received": "1"},
            ],
        },
    )
    assert over_gr.status_code == 409
    assert over_gr.json()["error"]["code"] == "OVER_RECEIPT"

    # Terima penuh barang 3 (4 dari 4) -> seluruh baris selesai dan ada qty_closed > 0 -> PO otomatis CLOSED
    gr2 = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po_id,
            "received_date": today,
            "lines": [
                {"po_line_id": l3_id, "location_id": ctx["loc"]["id"], "qty_received": "4"},
            ],
        },
    )
    assert gr2.status_code == 201
    assert (
        client.post(
            f"/api/v1/goods-receipts/{gr2.json()['id']}/post",
            headers=staff_user["auth_headers"],
        ).status_code
        == 200
    )

    po_final = client.get(
        f"/api/v1/purchase-orders/{po_id}",
        headers=purchasing_user["auth_headers"],
    )
    assert po_final.status_code == 200
    assert po_final.json()["status"] == "CLOSED"
    assert po_final.json()["closed_reason"]
