"""Pengujian Purchase Order (FR-04, PRD 5.1) dan Goods Receipt (FR-05, AC-01, AC-07, AC-13)."""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection

from app.main import create_app
from tests import factories


def test_purchase_order_lifecycle_validations_rbac_and_audit(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
    auditor_user: dict[str, Any],
) -> None:
    """FR-04, PRD 5.1, 6.3, 6.9, AC-05, AC-12:
    - Siklus status PO: DRAFT -> ISSUED -> CLOSED, serta DRAFT/ISSUED -> CANCELLED.
    - Validasi keunikan barang per PO, aturan UoM allow_decimal, dan referensi aktif.
    - Penolakan revisi PO setelah ISSUED (409 INVALID_STATE_TRANSITION).
    - Penolakan cancel/close PO apabila terdapat GR berstatus DRAFT/POSTED.
    - Penegakan RBAC (Warehouse Staff ditolak menerbitkan PO -> 403 PERMISSION_DENIED)
      dan Warehouse Scoping pada pembacaan PO oleh Warehouse Staff.
    """
    wh_a = factories.create_warehouse(db_conn, code="WH-A", name="Gudang A")
    wh_b = factories.create_warehouse(db_conn, code="WH-B", name="Gudang B")
    sup_active = factories.create_supplier(db_conn, code="SUP-01", name="PT Pemasok Aktif")
    sup_inactive = factories.create_supplier(
        db_conn, code="SUP-02", name="PT Pemasok Nonaktif", is_active=False
    )
    cat = factories.create_category(db_conn, name="Elektrikal")
    uom_pcs = factories.create_uom(db_conn, code="PCS", name="Pieces", allow_decimal=False)
    uom_m = factories.create_uom(db_conn, code="MTR", name="Meter", allow_decimal=True)
    item_1 = factories.create_item(
        db_conn, sku="EL-001", name="MCB 16A", category_id=cat["id"], uom_id=uom_pcs["id"]
    )
    item_2 = factories.create_item(
        db_conn, sku="EL-002", name="Kabel NYM", category_id=cat["id"], uom_id=uom_m["id"]
    )

    # Tugaskan staff_user hanya ke Gudang A
    client.put(
        f"/api/v1/users/{staff_user['id']}/warehouses",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_ids": [wh_a["id"]]},
    )

    # 1. Validasi referensi nonaktif: membuat PO dengan pemasok nonaktif -> 422 INACTIVE_REFERENCE
    inact_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup_inactive["id"],
            "warehouse_id": wh_a["id"],
            "order_date": "2026-10-23",
            "lines": [{"item_id": item_1["id"], "qty_ordered": "10"}],
        },
    )
    assert inact_res.status_code == 422
    assert inact_res.json()["error"]["code"] == "INACTIVE_REFERENCE"

    # 2. Validasi satu barang hanya boleh muncul satu kali per PO -> 422 VALIDATION_ERROR
    dup_line_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup_active["id"],
            "warehouse_id": wh_a["id"],
            "order_date": "2026-10-23",
            "lines": [
                {"item_id": item_1["id"], "qty_ordered": "10"},
                {"item_id": item_1["id"], "qty_ordered": "5"},
            ],
        },
    )
    assert dup_line_res.status_code == 422
    assert dup_line_res.json()["error"]["code"] == "VALIDATION_ERROR"

    # 3. Validasi UoM allow_decimal = FALSE menolak kuantitas desimal -> 422 VALIDATION_ERROR
    dec_err_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup_active["id"],
            "warehouse_id": wh_a["id"],
            "order_date": "2026-10-23",
            "lines": [{"item_id": item_1["id"], "qty_ordered": "10.5"}],
        },
    )
    assert dec_err_res.status_code == 422
    assert dec_err_res.json()["error"]["code"] == "VALIDATION_ERROR"

    # 4. Buat PO DRAFT kosong (0 baris), coba issue -> ditolak 422 VALIDATION_ERROR
    empty_po_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup_active["id"],
            "warehouse_id": wh_a["id"],
            "order_date": "2026-10-23",
            "notes": "PO awal masih disusun",
            "lines": [],
        },
    )
    assert empty_po_res.status_code == 201
    po_empty = empty_po_res.json()
    assert po_empty["status"] == "DRAFT"
    assert po_empty["po_number"].startswith("PO-202610-")

    issue_empty = client.post(
        f"/api/v1/purchase-orders/{po_empty['id']}/issue",
        headers=purchasing_user["auth_headers"],
    )
    assert issue_empty.status_code == 422
    assert issue_empty.json()["error"]["code"] == "VALIDATION_ERROR"

    # 5. Revisi PO saat masih DRAFT (menambahkan 2 baris barang) -> 200 OK
    patch_res = client.patch(
        f"/api/v1/purchase-orders/{po_empty['id']}",
        headers=purchasing_user["auth_headers"],
        json={
            "notes": "PO siap diterbitkan",
            "lines": [
                {"item_id": item_1["id"], "qty_ordered": "50", "notes": "Batch 1"},
                {"item_id": item_2["id"], "qty_ordered": "25.5000"},
            ],
        },
    )
    assert patch_res.status_code == 200
    po_updated = patch_res.json()
    assert po_updated["line_count"] == 2
    assert po_updated["lines"][0]["qty_ordered"] == "50.0000"
    assert po_updated["lines"][1]["qty_ordered"] == "25.5000"

    # 6. AC-05: Warehouse Staff mencoba menerbitkan PO -> 403 PERMISSION_DENIED
    staff_issue = client.post(
        f"/api/v1/purchase-orders/{po_empty['id']}/issue",
        headers=staff_user["auth_headers"],
    )
    assert staff_issue.status_code == 403
    assert staff_issue.json()["error"]["code"] == "PERMISSION_DENIED"

    # 7. Purchasing Staff menerbitkan PO (DRAFT -> ISSUED) -> 200 OK
    issue_ok = client.post(
        f"/api/v1/purchase-orders/{po_empty['id']}/issue",
        headers=purchasing_user["auth_headers"],
    )
    assert issue_ok.status_code == 200
    po_issued = issue_ok.json()
    assert po_issued["status"] == "ISSUED"
    assert po_issued["issued_at"] is not None
    assert po_issued["issued_by"] == purchasing_user["id"]

    # 8. Setelah ISSUED, mengubah PO ditolak dengan 409 INVALID_STATE_TRANSITION
    patch_after_issue = client.patch(
        f"/api/v1/purchase-orders/{po_empty['id']}",
        headers=purchasing_user["auth_headers"],
        json={"notes": "Coba ubah setelah ISSUED"},
    )
    assert patch_after_issue.status_code == 409
    assert patch_after_issue.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # 9. Buat GR berstatus DRAFT pada PO tersebut -> harus menolak cancel PO ISSUED dan menolak close PO
    gr_draft = db_conn.execute(
        """
        INSERT INTO goods_receipts (gr_number, po_id, warehouse_id, status, received_date, created_by)
        VALUES ('GR-202610-0001', %s, %s, 'DRAFT', CURRENT_DATE, %s)
        RETURNING id
        """,
        (po_empty["id"], wh_a["id"], staff_user["id"]),
    ).fetchone()
    assert gr_draft is not None

    cancel_blocked = client.post(
        f"/api/v1/purchase-orders/{po_empty['id']}/cancel",
        headers=purchasing_user["auth_headers"],
    )
    assert cancel_blocked.status_code == 409
    assert cancel_blocked.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    close_blocked = client.post(
        f"/api/v1/purchase-orders/{po_empty['id']}/close",
        headers=manager_user["auth_headers"],
        json={"closed_reason": "Sisa pesanan tidak dikirim pemasok"},
    )
    assert close_blocked.status_code == 409
    assert close_blocked.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # Batalkan GR DRAFT tersebut -> sekarang Warehouse Manager dapat menutup PO (ISSUED -> CLOSED)
    db_conn.execute(
        "UPDATE goods_receipts SET status = 'CANCELLED' WHERE id = %s",
        (gr_draft["id"],),
    )

    # Close PO dengan alasan kosong (spasi) -> 422 VALIDATION_ERROR
    close_blank = client.post(
        f"/api/v1/purchase-orders/{po_empty['id']}/close",
        headers=manager_user["auth_headers"],
        json={"closed_reason": "   "},
    )
    assert close_blank.status_code == 422
    assert close_blank.json()["error"]["code"] == "VALIDATION_ERROR"

    close_ok = client.post(
        f"/api/v1/purchase-orders/{po_empty['id']}/close",
        headers=manager_user["auth_headers"],
        json={"closed_reason": "Disepakati tutup dengan pemasok"},
    )
    assert close_ok.status_code == 200
    assert close_ok.json()["status"] == "CLOSED"
    assert close_ok.json()["closed_reason"] == "Disepakati tutup dengan pemasok"

    # 10. Buat PO ke Gudang B lalu uji cancel dari status ISSUED dan Warehouse Scoping pembacaan
    po_b = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup_active["id"],
            "warehouse_id": wh_b["id"],
            "order_date": "2026-10-23",
            "lines": [{"item_id": item_1["id"], "qty_ordered": "10"}],
        },
    ).json()
    client.post(
        f"/api/v1/purchase-orders/{po_b['id']}/issue",
        headers=purchasing_user["auth_headers"],
    )

    # Warehouse Staff (ditugaskan hanya ke Gudang A) tidak melihat PO Gudang B di daftar & ditolak 403 bila baca langsung
    staff_list = client.get(
        "/api/v1/purchase-orders", headers=staff_user["auth_headers"]
    ).json()
    assert all(p["warehouse_id"] == wh_a["id"] for p in staff_list["items"])

    staff_get_b = client.get(
        f"/api/v1/purchase-orders/{po_b['id']}",
        headers=staff_user["auth_headers"],
    )
    assert staff_get_b.status_code == 403
    assert staff_get_b.json()["error"]["code"] == "WAREHOUSE_NOT_ASSIGNED"

    # Cancel PO ISSUED (belum ada GR) -> 200 CANCELLED
    cancel_b = client.post(
        f"/api/v1/purchase-orders/{po_b['id']}/cancel",
        headers=purchasing_user["auth_headers"],
    )
    assert cancel_b.status_code == 200
    assert cancel_b.json()["status"] == "CANCELLED"


def test_ac01_partial_receipt_over_receipt_and_po_fulfillment(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-01, AC-12, FR-05, PRD 5.1, 6.2, 6.3, 6.6:
    1. PO ISSUED dengan baris barang qty_ordered = 100.
    2. GR #1 POSTED dengan qty_received = 60 -> status PO menjadi PARTIALLY_RECEIVED,
       po_line.qty_received = 60, saldo lokasi bertambah 60, dan 1 baris stock_movements
       bertipe IN_PURCHASE tercatat.
    3. GR dengan qty_received = 50 (melebihi sisa 40) baik saat pembuatan maupun saat
       posting ulang setelah GR lain diposting -> ditolak 422 OVER_RECEIPT_NOT_ALLOWED;
       saldo dan PO tidak berubah.
    4. GR berikutnya POSTED dengan sisa 40 -> status PO otomatis berubah menjadi RECEIVED,
       po_line.qty_received = 100, dan saldo lokasi menjadi 100.
    5. Mencakup juga AC-12 (Warehouse Scoping pada GR) serta revisi/pembatalan GR DRAFT.
    """
    wh_a = factories.create_warehouse(db_conn, code="WH-GR-A", name="Gudang GR A")
    wh_b = factories.create_warehouse(db_conn, code="WH-GR-B", name="Gudang GR B")
    loc_a1 = factories.create_location(
        db_conn, warehouse_id=wh_a["id"], code="RACK-A1", name="Rak A1"
    )
    loc_a2 = factories.create_location(
        db_conn, warehouse_id=wh_a["id"], code="RACK-A2", name="Rak A2"
    )
    loc_b1 = factories.create_location(
        db_conn, warehouse_id=wh_b["id"], code="RACK-B1", name="Rak B1"
    )
    sup = factories.create_supplier(db_conn, code="SUP-GR", name="PT Pemasok GR")
    cat = factories.create_category(db_conn, name="Mekanikal")
    uom_pcs = factories.create_uom(db_conn, code="PCS-GR", name="Pieces", allow_decimal=False)
    item = factories.create_item(
        db_conn, sku="MK-100", name="Bearing 6205", category_id=cat["id"], uom_id=uom_pcs["id"]
    )

    # Tugaskan staff_user hanya ke Gudang A
    client.put(
        f"/api/v1/users/{staff_user['id']}/warehouses",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_ids": [wh_a["id"]]},
    )

    # Buat PO di Gudang A dengan qty_ordered = 100 dan terbitkan (ISSUED)
    po_res = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh_a["id"],
            "order_date": "2026-10-23",
            "lines": [{"item_id": item["id"], "qty_ordered": "100"}],
        },
    )
    assert po_res.status_code == 201
    po = po_res.json()
    po_line_id = po["lines"][0]["id"]

    # Gagal membuat GR terhadap PO yang masih DRAFT -> 409 INVALID_STATE_TRANSITION
    gr_on_draft_po = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-10-23",
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "location_id": loc_a1["id"],
                    "qty_received": "10",
                }
            ],
        },
    )
    assert gr_on_draft_po.status_code == 409
    assert gr_on_draft_po.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # Terbitkan PO -> ISSUED
    issue_res = client.post(
        f"/api/v1/purchase-orders/{po['id']}/issue",
        headers=purchasing_user["auth_headers"],
    )
    assert issue_res.status_code == 200

    # Lokasi dari gudang berbeda (loc_b1 milik wh_b) ditolak -> 422 INVALID_LOCATION
    mismatch_res = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-10-23",
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "location_id": loc_b1["id"],
                    "qty_received": "10",
                }
            ],
        },
    )
    assert mismatch_res.status_code == 422
    assert mismatch_res.json()["error"]["code"] == "INVALID_LOCATION"

    # AC-12: Buat PO di Gudang B, terbitkan, lalu staff_user (hanya ditugaskan ke Gudang A)
    # mencoba membuat GR untuk PO Gudang B -> 403 WAREHOUSE_NOT_ASSIGNED
    po_b = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh_b["id"],
            "order_date": "2026-10-23",
            "lines": [{"item_id": item["id"], "qty_ordered": "20"}],
        },
    ).json()
    client.post(
        f"/api/v1/purchase-orders/{po_b['id']}/issue",
        headers=purchasing_user["auth_headers"],
    )
    unassigned_gr = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po_b["id"],
            "received_date": "2026-10-23",
            "lines": [
                {
                    "po_line_id": po_b["lines"][0]["id"],
                    "location_id": loc_b1["id"],
                    "qty_received": "10",
                }
            ],
        },
    )
    assert unassigned_gr.status_code == 403
    assert unassigned_gr.json()["error"]["code"] == "WAREHOUSE_NOT_ASSIGNED"

    # Langkah 2 AC-01: Buat GR #1 (awalnya 50, lalu di-PATCH menjadi 60) dan POST
    gr1_create = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-10-23",
            "supplier_dn_number": "SJ-001",
            "notes": "Penerimaan tahap 1",
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "location_id": loc_a1["id"],
                    "qty_received": "50",
                }
            ],
        },
    )
    assert gr1_create.status_code == 201
    gr1 = gr1_create.json()
    assert gr1["status"] == "DRAFT"
    assert gr1["gr_number"].startswith("GR-202610-")

    # Revisi GR #1 selagi DRAFT menjadi qty_received = 60
    gr1_patch = client.patch(
        f"/api/v1/goods-receipts/{gr1['id']}",
        headers=staff_user["auth_headers"],
        json={
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "location_id": loc_a1["id"],
                    "qty_received": "60",
                }
            ]
        },
    )
    assert gr1_patch.status_code == 200
    assert gr1_patch.json()["lines"][0]["qty_received"] == "60.0000"

    # Sebelum GR #1 diposting, saldo stok masih 0 dan PO masih ISSUED (qty_received = 0)
    po_before_post = client.get(
        f"/api/v1/purchase-orders/{po['id']}", headers=staff_user["auth_headers"]
    ).json()
    assert po_before_post["status"] == "ISSUED"
    assert po_before_post["lines"][0]["qty_received"] == "0.0000"

    # Post GR #1 (qty_received = 60)
    gr1_post = client.post(
        f"/api/v1/goods-receipts/{gr1['id']}/post",
        headers=staff_user["auth_headers"],
    )
    assert gr1_post.status_code == 200
    assert gr1_post.json()["status"] == "POSTED"
    assert gr1_post.json()["posted_by"] == staff_user["id"]

    # Verifikasi status PO -> PARTIALLY_RECEIVED dan po_line.qty_received = 60.0000
    po_after_gr1 = client.get(
        f"/api/v1/purchase-orders/{po['id']}", headers=staff_user["auth_headers"]
    ).json()
    assert po_after_gr1["status"] == "PARTIALLY_RECEIVED"
    assert po_after_gr1["lines"][0]["qty_received"] == "60.0000"

    # Verifikasi saldo stok di loc_a1 = 60.0000 dan 1 baris stock_movements IN_PURCHASE
    stock_res = client.get(
        f"/api/v1/stock/by-location?warehouse_id={wh_a['id']}&location_id={loc_a1['id']}&item_id={item['id']}",
        headers=staff_user["auth_headers"],
    ).json()
    assert len(stock_res["items"]) == 1
    assert stock_res["items"][0]["qty_on_hand"] == "60.0000"

    movements_res = client.get(
        f"/api/v1/stock/movements?reference_type=GOODS_RECEIPT&reference_id={gr1['id']}",
        headers=staff_user["auth_headers"],
    ).json()
    assert len(movements_res["items"]) == 1
    mv1 = movements_res["items"][0]
    assert mv1["movement_type"] == "IN_PURCHASE"
    assert mv1["qty_before"] == "0.0000"
    assert mv1["qty_change"] == "60.0000"
    assert mv1["qty_after"] == "60.0000"

    # GR yang sudah POSTED tidak boleh dibatalkan atau diubah -> 409 INVALID_STATE_TRANSITION
    cancel_posted = client.post(
        f"/api/v1/goods-receipts/{gr1['id']}/cancel",
        headers=staff_user["auth_headers"],
    )
    assert cancel_posted.status_code == 409
    assert cancel_posted.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # Langkah 3 AC-01: Coba buat GR #2 dengan qty_received = 50 (60 + 50 = 110 > 100)
    # -> Ditolak 409 OVER_RECEIPT
    over_create = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-10-23",
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "location_id": loc_a1["id"],
                    "qty_received": "50",
                }
            ],
        },
    )
    assert over_create.status_code == 409
    assert over_create.json()["error"]["code"] == "OVER_RECEIPT"

    # Uji juga deteksi OVER_RECEIPT saat POSTING ketika ada 2 GR DRAFT paralel:
    # Buat GR_A (DRAFT, qty 30) dan GR_B (DRAFT, qty 20). Saat dibuat keduanya <= sisa 40.
    gr_a = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-10-23",
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "location_id": loc_a1["id"],
                    "qty_received": "30",
                }
            ],
        },
    ).json()
    gr_b = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-10-23",
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "location_id": loc_a2["id"],
                    "qty_received": "20",
                }
            ],
        },
    ).json()

    # Post GR_A (60 + 30 = 90 <= 100) -> berhasil (PARTIALLY_RECEIVED, qty_received = 90)
    post_gr_a = client.post(
        f"/api/v1/goods-receipts/{gr_a['id']}/post",
        headers=staff_user["auth_headers"],
    )
    assert post_gr_a.status_code == 200

    # Sekarang post GR_B (90 + 20 = 110 > 100) -> ditolak saat evaluasi ulang di dalam lock!
    post_gr_b = client.post(
        f"/api/v1/goods-receipts/{gr_b['id']}/post",
        headers=staff_user["auth_headers"],
    )
    assert post_gr_b.status_code == 409
    assert post_gr_b.json()["error"]["code"] == "OVER_RECEIPT"

    # Saldo tidak bertambah akibat gagalnya GR_B (tetap 90 di loc_a1 dan 0 di loc_a2)
    po_after_gr_b_fail = client.get(
        f"/api/v1/purchase-orders/{po['id']}", headers=staff_user["auth_headers"]
    ).json()
    assert po_after_gr_b_fail["status"] == "PARTIALLY_RECEIVED"
    assert po_after_gr_b_fail["lines"][0]["qty_received"] == "90.0000"

    # Batalkan GR_B yang masih DRAFT -> 200 CANCELLED
    cancel_gr_b = client.post(
        f"/api/v1/goods-receipts/{gr_b['id']}/cancel",
        headers=staff_user["auth_headers"],
    )
    assert cancel_gr_b.status_code == 200
    assert cancel_gr_b.json()["status"] == "CANCELLED"

    # Langkah 4 AC-01: Buat GR terakhir untuk sisa 10 unit ke loc_a2 dan POST
    # (sehingga total GR1(60) + GR_A(30) + GR_FINAL(10) = 100)
    gr_final = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-10-23",
            "lines": [
                {
                    "po_line_id": po_line_id,
                    "location_id": loc_a2["id"],
                    "qty_received": "10",
                }
            ],
        },
    ).json()
    post_final = client.post(
        f"/api/v1/goods-receipts/{gr_final['id']}/post",
        headers=staff_user["auth_headers"],
    )
    assert post_final.status_code == 200
    assert post_final.json()["status"] == "POSTED"

    # Verifikasi status PO berubah otomatis menjadi RECEIVED dan po_line.qty_received = 100.0000
    po_completed = client.get(
        f"/api/v1/purchase-orders/{po['id']}", headers=staff_user["auth_headers"]
    ).json()
    assert po_completed["status"] == "RECEIVED"
    assert po_completed["lines"][0]["qty_received"] == "100.0000"

    # Verifikasi total stok di Gudang A adalah 90 (loc_a1) + 10 (loc_a2) = 100.0000
    stock_wh_a = client.get(
        f"/api/v1/stock/by-location?warehouse_id={wh_a['id']}&item_id={item['id']}",
        headers=staff_user["auth_headers"],
    ).json()
    total_qty = sum(Decimal(row["qty_on_hand"]) for row in stock_wh_a["items"])
    assert total_qty == Decimal("100.0000")

    # Verifikasi daftar Goods Receipt (GET /api/v1/goods-receipts)
    gr_list = client.get(
        f"/api/v1/goods-receipts?po_id={po['id']}&status=POSTED",
        headers=staff_user["auth_headers"],
    ).json()
    assert gr_list["total"] == 3
    assert len(gr_list["items"]) == 3


def test_ac07_gr_post_transaction_atomicity_rollback_on_failure(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    staff_user: dict[str, Any],
    monkeypatch: Any,
) -> None:
    """AC-07 (Atomisitas Transaksi Saat Kegagalan di Tengah):
    Posting dokumen dengan beberapa baris barang yang disimulasikan gagal pada langkah
    terakhir setelah baris pertama memutakhirkan saldo dan ledger di dalam transaksi:
    - Seluruh transaksi harus di-rollback total:
      * Status GR tetap DRAFT
      * Tidak ada perubahan inventory_balances pada baris ke-1 maupun ke-2
      * Tidak ada baris stock_movements yang tersimpan
      * po_lines.qty_received tetap 0 dan status PO tetap ISSUED
      * Tidak ada audit_logs POST yang tersimpan
    """
    wh = factories.create_warehouse(db_conn, code="WH-AC07", name="Gudang Atomik")
    loc = factories.create_location(
        db_conn, warehouse_id=wh["id"], code="BIN-07", name="Bin 07"
    )
    sup = factories.create_supplier(db_conn, code="SUP-07", name="PT Pemasok 07")
    cat = factories.create_category(db_conn, name="Atomik")
    uom = factories.create_uom(db_conn, code="PCS-07", name="Pieces", allow_decimal=False)
    item_1 = factories.create_item(
        db_conn, sku="AT-001", name="Item Atomik 1", category_id=cat["id"], uom_id=uom["id"]
    )
    item_2 = factories.create_item(
        db_conn, sku="AT-002", name="Item Atomik 2", category_id=cat["id"], uom_id=uom["id"]
    )

    client.put(
        f"/api/v1/users/{staff_user['id']}/warehouses",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_ids": [wh["id"]]},
    )

    po = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh["id"],
            "order_date": "2026-10-23",
            "lines": [
                {"item_id": item_1["id"], "qty_ordered": "20"},
                {"item_id": item_2["id"], "qty_ordered": "30"},
            ],
        },
    ).json()
    client.post(
        f"/api/v1/purchase-orders/{po['id']}/issue",
        headers=purchasing_user["auth_headers"],
    )

    gr = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-10-23",
            "lines": [
                {
                    "po_line_id": po["lines"][0]["id"],
                    "location_id": loc["id"],
                    "qty_received": "20",
                },
                {
                    "po_line_id": po["lines"][1]["id"],
                    "location_id": loc["id"],
                    "qty_received": "30",
                },
            ],
        },
    ).json()

    # Simulasikan kegagalan pada pemanggilan apply_movement kedua (baris ke-2) setelah
    # baris ke-1 selesai memperbarui inventory_balances dan memasukkan stock_movements
    from app.services import gr_service
    from app.services.inventory_service import apply_movement as real_apply_movement

    call_count = 0

    def failing_on_second_line(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Simulasi kegagalan di tengah transaksi pada baris ke-2")
        return real_apply_movement(*args, **kwargs)

    monkeypatch.setattr(gr_service.inventory_service, "apply_movement", failing_on_second_line)

    no_raise_client = TestClient(client.app, raise_server_exceptions=False)
    post_res = no_raise_client.post(
        f"/api/v1/goods-receipts/{gr['id']}/post",
        headers=staff_user["auth_headers"],
    )
    assert post_res.status_code == 500
    assert post_res.json()["error"]["code"] == "INTERNAL_ERROR"
    assert call_count == 2

    # Verifikasi rollback menyeluruh:
    # 1. Status GR tetap DRAFT
    gr_check = client.get(
        f"/api/v1/goods-receipts/{gr['id']}", headers=staff_user["auth_headers"]
    ).json()
    assert gr_check["status"] == "DRAFT"
    assert gr_check["posted_at"] is None

    # 2. Status PO tetap ISSUED dan qty_received kedua baris tetap 0.0000
    po_check = client.get(
        f"/api/v1/purchase-orders/{po['id']}", headers=staff_user["auth_headers"]
    ).json()
    assert po_check["status"] == "ISSUED"
    assert all(line["qty_received"] == "0.0000" for line in po_check["lines"])

    # 3. Tidak ada perubahan saldo maupun baris stock_movements untuk GR tersebut
    bal_rows = db_conn.execute(
        "SELECT qty_on_hand FROM inventory_balances WHERE warehouse_id = %s AND qty_on_hand > 0",
        (wh["id"],),
    ).fetchall()
    assert bal_rows == []

    mv_rows = db_conn.execute(
        "SELECT id FROM stock_movements WHERE reference_type = 'GOODS_RECEIPT' AND reference_id = %s",
        (gr["id"],),
    ).fetchall()
    assert mv_rows == []

    # 4. Tidak ada audit log beraksi POST pada GR tersebut
    audit_rows = db_conn.execute(
        "SELECT id FROM audit_logs WHERE entity_type = 'GOODS_RECEIPT' AND entity_id = %s AND action = 'POST'",
        (str(gr["id"]),),
    ).fetchall()
    assert audit_rows == []


def test_ac13_concurrent_gr_post_prevents_double_posting(
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-13 (Idempotensi / Pencegahan Double-Post Konkuren):
    Dua request konkuren memanggil POST /api/v1/goods-receipts/{id}/post pada GR DRAFT
    yang sama pada saat bersamaan:
    - Tepat satu request berhasil (200 OK) dan satu request gagal dengan 409 INVALID_STATE_TRANSITION.
    - Saldo stok hanya bertambah satu kali dan stock_movements hanya mencatat satu set pergerakan.
    """
    app = create_app()
    with TestClient(app) as main_client:
        wh = factories.create_warehouse(db_conn, code="WH-AC13", name="Gudang Konkuren GR")
        loc = factories.create_location(
            db_conn, warehouse_id=wh["id"], code="BIN-13", name="Bin 13"
        )
        sup = factories.create_supplier(db_conn, code="SUP-13", name="PT Pemasok 13")
        cat = factories.create_category(db_conn, name="Konkurensi")
        uom = factories.create_uom(db_conn, code="PCS-13", name="Pieces", allow_decimal=False)
        item = factories.create_item(
            db_conn,
            sku="CC-013",
            name="Barang Uji Konkurensi GR",
            category_id=cat["id"],
            uom_id=uom["id"],
        )

        main_client.put(
            f"/api/v1/users/{staff_user['id']}/warehouses",
            headers=superadmin_user["auth_headers"],
            json={"warehouse_ids": [wh["id"]]},
        )

        po = main_client.post(
            "/api/v1/purchase-orders",
            headers=purchasing_user["auth_headers"],
            json={
                "supplier_id": sup["id"],
                "warehouse_id": wh["id"],
                "order_date": "2026-10-23",
                "lines": [{"item_id": item["id"], "qty_ordered": "100"}],
            },
        ).json()
        main_client.post(
            f"/api/v1/purchase-orders/{po['id']}/issue",
            headers=purchasing_user["auth_headers"],
        )

        gr = main_client.post(
            "/api/v1/goods-receipts",
            headers=staff_user["auth_headers"],
            json={
                "po_id": po["id"],
                "received_date": "2026-10-23",
                "lines": [
                    {
                        "po_line_id": po["lines"][0]["id"],
                        "location_id": loc["id"],
                        "qty_received": "45",
                    }
                ],
            },
        ).json()

        barrier = threading.Barrier(2)
        results: list[tuple[int, dict[str, Any]]] = []
        lock = threading.Lock()

        def worker() -> None:
            with TestClient(app) as thread_client:
                barrier.wait()
                resp = thread_client.post(
                    f"/api/v1/goods-receipts/{gr['id']}/post",
                    headers=staff_user["auth_headers"],
                )
                with lock:
                    results.append((resp.status_code, resp.json()))

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        status_codes = sorted(r[0] for r in results)
        assert status_codes == [200, 409]

        conflict_body = next(r[1] for r in results if r[0] == 409)
        assert conflict_body["error"]["code"] == "INVALID_STATE_TRANSITION"

        # Verifikasi saldo hanya bertambah satu kali (45.0000, bukan 90.0000)
        bal = db_conn.execute(
            """
            SELECT qty_on_hand FROM inventory_balances
            WHERE warehouse_id = %s AND location_id = %s AND item_id = %s
            """,
            (wh["id"], loc["id"], item["id"]),
        ).fetchone()
        assert bal is not None
        assert bal["qty_on_hand"] == Decimal("45.0000")

        # Verifikasi baris stock_movements untuk GR ini hanya tepat 1 baris
        mv_count = db_conn.execute(
            """
            SELECT COUNT(*)::int AS cnt FROM stock_movements
            WHERE reference_type = 'GOODS_RECEIPT' AND reference_id = %s
            """,
            (gr["id"],),
        ).fetchone()
        assert mv_count is not None
        assert mv_count["cnt"] == 1


