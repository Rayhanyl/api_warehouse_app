"""Pengujian Stock Opname & Pembekuan Lokasi (FR-07, PRD 5.1, 6.5, 6.6, AC-04, AC-05, AC-10, AC-12)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection

from app.services import inventory_service
from tests import factories


def _seed_stock(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int,
    item_id: int,
    qty: Decimal,
    actor_id: int,
    ref_id: int = 1,
) -> None:
    with conn.transaction():
        inventory_service.apply_movement(
            conn,
            movement_type="IN_PURCHASE",
            warehouse_id=warehouse_id,
            location_id=location_id,
            item_id=item_id,
            qty_change=qty,
            reference_type="GOODS_RECEIPT",
            reference_id=ref_id,
            created_by=actor_id,
            notes="Seed saldo awal pengujian Opname",
        )


def test_ac04_stock_opname_reconciliation_variance_and_zero_variance_no_ledger(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-04, AC-05, FR-07, PRD 5.1, 5.2.3, 5.2.4:
    - Given sebuah sesi Stock Opname di mana:
      * Barang 1 tercatat qty_system = 100 unit dan petugas memasukkan qty_physical = 97 unit (qty_variance = -3)
      * Barang 2 tercatat qty_system = 50 unit dan petugas memasukkan qty_physical = 50 unit (qty_variance = 0)
      * Barang 3 ditemukan secara fisik tanpa saldo awal (qty_system = 0) dan diisi qty_physical = 12 unit (qty_variance = +12)
    - Mencakup penolakan persetujuan oleh Warehouse Staff (AC-05 -> 403 PERMISSION_DENIED),
      serta alur reject (WAITING_APPROVAL -> IN_PROGRESS) dengan alasan wajib sebelum diajukan ulang.
    - When Warehouse Manager menyetujui opname menjadi COMPLETED:
      * Barang 1: qty_variance = -3.0000, saldo menjadi 97.0000, tercatat 1 baris ADJUSTMENT_MINUS
        (qty_before = 100.0000, qty_change = -3.0000, qty_after = 97.0000).
      * Barang 2 (selisih 0): saldo tetap 50.0000 dan TIDAK menghasilkan baris stock_movements.
      * Barang 3 (saldo awal): qty_variance = +12.0000, saldo menjadi 12.0000, tercatat 1 baris ADJUSTMENT_PLUS
        (qty_before = 0.0000, qty_change = +12.0000, qty_after = 12.0000).
    """
    wh = factories.create_warehouse(db_conn, code="WH-AC04", name="Gudang Opname AC04")
    loc_1 = factories.create_location(
        db_conn, warehouse_id=wh["id"], code="RACK-04-1", name="Rak 04-1"
    )
    loc_2 = factories.create_location(
        db_conn, warehouse_id=wh["id"], code="RACK-04-2", name="Rak 04-2"
    )
    cat = factories.create_category(db_conn, name="Suku Cadang Opname")
    uom = factories.create_uom(db_conn, code="PCS-04", name="Pieces", allow_decimal=False)
    item_1 = factories.create_item(
        db_conn, sku="OP-100", name="Baut M10", category_id=cat["id"], uom_id=uom["id"]
    )
    item_2 = factories.create_item(
        db_conn, sku="OP-050", name="Mur M10", category_id=cat["id"], uom_id=uom["id"]
    )
    item_3 = factories.create_item(
        db_conn, sku="OP-NEW", name="Ring Plat M10", category_id=cat["id"], uom_id=uom["id"]
    )

    for usr in (manager_user, staff_user):
        client.put(
            f"/api/v1/users/{usr['id']}/warehouses",
            headers=superadmin_user["auth_headers"],
            json={"warehouse_ids": [wh["id"]]},
        )

    # Seed saldo sistem: item_1 = 100 unit, item_2 = 50 unit di loc_1
    _seed_stock(
        db_conn,
        warehouse_id=wh["id"],
        location_id=loc_1["id"],
        item_id=item_1["id"],
        qty=Decimal("100.0000"),
        actor_id=superadmin_user["id"],
        ref_id=10,
    )
    _seed_stock(
        db_conn,
        warehouse_id=wh["id"],
        location_id=loc_1["id"],
        item_id=item_2["id"],
        qty=Decimal("50.0000"),
        actor_id=superadmin_user["id"],
        ref_id=11,
    )

    # 1. Buat sesi Opname (awalnya seluruh gudang, lalu PATCH ke loc_1 saat masih DRAFT)
    create_res = client.post(
        "/api/v1/stock-opnames",
        headers=manager_user["auth_headers"],
        json={"warehouse_id": wh["id"], "notes": "Opname bulanan"},
    )
    assert create_res.status_code == 201
    opname = create_res.json()
    assert opname["status"] == "DRAFT"
    assert opname["opname_number"].startswith("OPN-")

    patch_res = client.patch(
        f"/api/v1/stock-opnames/{opname['id']}",
        headers=manager_user["auth_headers"],
        json={"location_id": loc_1["id"], "notes": "Opname khusus Rak 04-1"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["location_id"] == loc_1["id"]

    # 2. Mulai sesi Opname (DRAFT -> IN_PROGRESS) -> mengambil snapshot 2 baris (item_1=100, item_2=50)
    start_res = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/start",
        headers=manager_user["auth_headers"],
    )
    assert start_res.status_code == 200
    started = start_res.json()
    assert started["status"] == "IN_PROGRESS"
    assert started["line_count"] == 2

    line_item1 = next(ln for ln in started["lines"] if ln["item_id"] == item_1["id"])
    line_item2 = next(ln for ln in started["lines"] if ln["item_id"] == item_2["id"])
    assert line_item1["qty_system"] == "100.0000"
    assert line_item1["qty_physical"] is None
    assert line_item2["qty_system"] == "50.0000"
    assert line_item2["qty_physical"] is None

    # Coba submit sebelum seluruh baris diisi qty_physical -> ditolak 422 VALIDATION_ERROR
    early_submit = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/submit",
        headers=staff_user["auth_headers"],
    )
    assert early_submit.status_code == 422
    assert early_submit.json()["error"]["code"] == "VALIDATION_ERROR"

    # Coba tambah barang pada lokasi di luar cakupan sesi Opname (loc_2 padahal sesi khusus loc_1) -> 422 INVALID_LOCATION
    wrong_loc_count = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/count",
        headers=staff_user["auth_headers"],
        json={
            "lines": [
                {
                    "location_id": loc_2["id"],
                    "item_id": item_3["id"],
                    "qty_physical": "5",
                }
            ]
        },
    )
    assert wrong_loc_count.status_code == 422
    assert wrong_loc_count.json()["error"]["code"] == "INVALID_LOCATION"

    # 3. Petugas mengisi hasil hitung fisik (awal: item_1 = 95, item_2 = 50, tambah item_3 = 12 dengan qty_system = 0)
    count_res = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/count",
        headers=staff_user["auth_headers"],
        json={
            "lines": [
                {"line_id": line_item1["id"], "qty_physical": "95"},
                {"line_id": line_item2["id"], "qty_physical": "50"},
                {
                    "location_id": loc_1["id"],
                    "item_id": item_3["id"],
                    "qty_physical": "12",
                    "notes": "Barang ditemukan di rak bawah",
                },
            ]
        },
    )
    assert count_res.status_code == 200
    assert count_res.json()["line_count"] == 3

    # 4. Submit sesi Opname (IN_PROGRESS -> WAITING_APPROVAL)
    submit_res = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/submit",
        headers=staff_user["auth_headers"],
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "WAITING_APPROVAL"

    # 5. AC-05: Warehouse Staff mencoba menyetujui akhir Stock Opname -> 403 PERMISSION_DENIED
    staff_approve = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/approve",
        headers=staff_user["auth_headers"],
    )
    assert staff_approve.status_code == 403
    assert staff_approve.json()["error"]["code"] == "PERMISSION_DENIED"

    # 6. Warehouse Manager menolak (WAITING_APPROVAL -> IN_PROGRESS) untuk hitung ulang item_1:
    #    Tanpa alasan ditolak 422 VALIDATION_ERROR; dengan alasan berhasil kembali ke IN_PROGRESS.
    reject_blank = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/reject",
        headers=manager_user["auth_headers"],
        json={"rejection_reason": "   "},
    )
    assert reject_blank.status_code == 422
    assert reject_blank.json()["error"]["code"] == "VALIDATION_ERROR"

    reject_ok = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/reject",
        headers=manager_user["auth_headers"],
        json={"rejection_reason": "Mohon hitung ulang Baut M10 di Rak 04-1"},
    )
    assert reject_ok.status_code == 200
    assert reject_ok.json()["status"] == "IN_PROGRESS"
    assert (
        reject_ok.json()["rejection_reason"]
        == "Mohon hitung ulang Baut M10 di Rak 04-1"
    )

    # 7. Petugas mengoreksi qty_physical item_1 menjadi 97 unit (sesuai skenario AC-04: 100 -> 97) lalu submit ulang
    recount_res = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/count",
        headers=staff_user["auth_headers"],
        json={
            "lines": [
                {
                    "line_id": line_item1["id"],
                    "qty_physical": "97",
                    "notes": "Hasil hitung ulang terverifikasi 97 unit",
                }
            ]
        },
    )
    assert recount_res.status_code == 200

    resubmit_res = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/submit",
        headers=staff_user["auth_headers"],
    )
    assert resubmit_res.status_code == 200
    assert resubmit_res.json()["status"] == "WAITING_APPROVAL"

    # 8. Warehouse Manager menyetujui Stock Opname (WAITING_APPROVAL -> COMPLETED)
    approve_res = client.post(
        f"/api/v1/stock-opnames/{opname['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    assert approve_res.status_code == 200
    completed = approve_res.json()
    assert completed["status"] == "COMPLETED"
    assert completed["approved_by"] == manager_user["id"]

    comp_line1 = next(ln for ln in completed["lines"] if ln["item_id"] == item_1["id"])
    comp_line2 = next(ln for ln in completed["lines"] if ln["item_id"] == item_2["id"])
    comp_line3 = next(ln for ln in completed["lines"] if ln["item_id"] == item_3["id"])

    # Verifikasi AC-04: qty_variance tercatat -3.0000 pada item_1, 0.0000 pada item_2, +12.0000 pada item_3
    assert comp_line1["qty_system"] == "100.0000"
    assert comp_line1["qty_physical"] == "97.0000"
    assert comp_line1["qty_variance"] == "-3.0000"

    assert comp_line2["qty_variance"] == "0.0000"

    assert comp_line3["qty_system"] == "0.0000"
    assert comp_line3["qty_physical"] == "12.0000"
    assert comp_line3["qty_variance"] == "12.0000"

    # Verifikasi saldo stok di inventory_balances
    balances = {
        int(row["item_id"]): row["qty_on_hand"]
        for row in db_conn.execute(
            "SELECT item_id, qty_on_hand FROM inventory_balances WHERE warehouse_id = %s AND location_id = %s",
            (wh["id"], loc_1["id"]),
        ).fetchall()
    }
    assert balances[item_1["id"]] == Decimal("97.0000")
    assert balances[item_2["id"]] == Decimal("50.0000")
    assert balances[item_3["id"]] == Decimal("12.0000")

    # Verifikasi stock_movements: hanya ada 2 baris untuk STOCK_OPNAME ini (item_1 ADJUSTMENT_MINUS, item_3 ADJUSTMENT_PLUS;
    # item_2 yang berselisih 0 TIDAK menghasilkan baris ledger!)
    movements = client.get(
        f"/api/v1/stock/movements?reference_type=STOCK_OPNAME&reference_id={opname['id']}",
        headers=superadmin_user["auth_headers"],
    ).json()
    assert movements["total"] == 2

    mv_item1 = next(m for m in movements["items"] if m["item_id"] == item_1["id"])
    assert mv_item1["movement_type"] == "ADJUSTMENT_MINUS"
    assert mv_item1["qty_before"] == "100.0000"
    assert mv_item1["qty_change"] == "-3.0000"
    assert mv_item1["qty_after"] == "97.0000"

    mv_item3 = next(m for m in movements["items"] if m["item_id"] == item_3["id"])
    assert mv_item3["movement_type"] == "ADJUSTMENT_PLUS"
    assert mv_item3["qty_before"] == "0.0000"
    assert mv_item3["qty_change"] == "12.0000"
    assert mv_item3["qty_after"] == "12.0000"


def test_ac10_location_freeze_during_opname_and_unfreeze_on_complete_or_cancel(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-10 & PRD 6.6 (Pembekuan Lokasi Selama Stock Opname):
    - Given sesi Opname berstatus IN_PROGRESS pada Lokasi X:
      1. Mencoba memulai sesi Opname lain yang menyentuh Lokasi X -> ditolak 409 LOCATION_FROZEN.
      2. Mencoba mem-posting Goods Receipt (GR) ke Lokasi X -> ditolak 409 LOCATION_FROZEN.
      3. Mencoba mengirim Transfer (SHIPPED) dari Lokasi X -> ditolak 409 LOCATION_FROZEN.
      4. Mencoba menerima Transfer (RECEIVED) yang sudah SHIPPED menuju Lokasi X -> ditolak 409 LOCATION_FROZEN
         (Transfer tetap menunggu di status SHIPPED / in-transit).
    - When sesi Opname dibatalkan (CANCELLED) atau diselesaikan (COMPLETED):
      * Seluruh transaksi (GR post, Transfer ship, Transfer receive) pada Lokasi X dapat dilakukan kembali (200 OK).
    """
    wh_a = factories.create_warehouse(db_conn, code="WH-AC10-A", name="Gudang A Opname")
    wh_b = factories.create_warehouse(db_conn, code="WH-AC10-B", name="Gudang B Transfer")
    loc_x = factories.create_location(
        db_conn, warehouse_id=wh_a["id"], code="LOC-X", name="Lokasi X"
    )
    loc_b = factories.create_location(
        db_conn, warehouse_id=wh_b["id"], code="LOC-B", name="Lokasi B"
    )
    sup = factories.create_supplier(db_conn, code="SUP-10", name="PT Pemasok 10")
    cat = factories.create_category(db_conn, name="Freeze Test")
    uom = factories.create_uom(db_conn, code="PCS-10", name="Pieces", allow_decimal=False)
    item = factories.create_item(
        db_conn, sku="FRZ-001", name="Barang Uji Freeze", category_id=cat["id"], uom_id=uom["id"]
    )

    for usr in (manager_user, staff_user):
        client.put(
            f"/api/v1/users/{usr['id']}/warehouses",
            headers=superadmin_user["auth_headers"],
            json={"warehouse_ids": [wh_a["id"], wh_b["id"]]},
        )

    # Seed stok 20 unit di Lokasi X (wh_a) dan 20 unit di Lokasi B (wh_b)
    _seed_stock(
        db_conn,
        warehouse_id=wh_a["id"],
        location_id=loc_x["id"],
        item_id=item["id"],
        qty=Decimal("20.0000"),
        actor_id=superadmin_user["id"],
        ref_id=20,
    )
    _seed_stock(
        db_conn,
        warehouse_id=wh_b["id"],
        location_id=loc_b["id"],
        item_id=item["id"],
        qty=Decimal("20.0000"),
        actor_id=superadmin_user["id"],
        ref_id=21,
    )

    # Siapkan:
    # (a) PO ISSUED + GR DRAFT menuju Lokasi X
    po = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh_a["id"],
            "order_date": "2026-10-23",
            "lines": [{"item_id": item["id"], "qty_ordered": "10"}],
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
                    "location_id": loc_x["id"],
                    "qty_received": "10",
                }
            ],
        },
    ).json()

    # (b) Transfer keluar dari Lokasi X -> Lokasi B berstatus APPROVED
    trf_out = client.post(
        "/api/v1/stock-transfers",
        headers=staff_user["auth_headers"],
        json={
            "source_warehouse_id": wh_a["id"],
            "source_location_id": loc_x["id"],
            "destination_warehouse_id": wh_b["id"],
            "destination_location_id": loc_b["id"],
            "lines": [{"item_id": item["id"], "qty": "5"}],
        },
    ).json()
    client.post(
        f"/api/v1/stock-transfers/{trf_out['id']}/approve",
        headers=manager_user["auth_headers"],
    )

    # (c) Transfer masuk dari Lokasi B -> Lokasi X yang sudah dikirim (SHIPPED) sebelum Lokasi X dibekukan
    trf_in = client.post(
        "/api/v1/stock-transfers",
        headers=staff_user["auth_headers"],
        json={
            "source_warehouse_id": wh_b["id"],
            "source_location_id": loc_b["id"],
            "destination_warehouse_id": wh_a["id"],
            "destination_location_id": loc_x["id"],
            "lines": [{"item_id": item["id"], "qty": "4"}],
        },
    ).json()
    client.post(
        f"/api/v1/stock-transfers/{trf_in['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    client.post(
        f"/api/v1/stock-transfers/{trf_in['id']}/ship",
        headers=staff_user["auth_headers"],
    )

    # 1. Mulai sesi Opname #1 pada Lokasi X (DRAFT -> IN_PROGRESS)
    opn1 = client.post(
        "/api/v1/stock-opnames",
        headers=manager_user["auth_headers"],
        json={"warehouse_id": wh_a["id"], "location_id": loc_x["id"]},
    ).json()
    start_opn1 = client.post(
        f"/api/v1/stock-opnames/{opn1['id']}/start",
        headers=manager_user["auth_headers"],
    )
    assert start_opn1.status_code == 200
    assert start_opn1.json()["status"] == "IN_PROGRESS"

    # Mencoba memulai sesi Opname kedua pada gudang/lokasi yang tumpang tindih -> 409 LOCATION_FROZEN
    opn_dup = client.post(
        "/api/v1/stock-opnames",
        headers=manager_user["auth_headers"],
        json={"warehouse_id": wh_a["id"], "location_id": None},
    ).json()
    start_dup = client.post(
        f"/api/v1/stock-opnames/{opn_dup['id']}/start",
        headers=manager_user["auth_headers"],
    )
    assert start_dup.status_code == 409
    assert start_dup.json()["error"]["code"] == "LOCATION_FROZEN"

    # 2. Selama Lokasi X dibekukan (IN_PROGRESS):
    #    - Posting GR ke Lokasi X ditolak 409 LOCATION_FROZEN
    gr_frozen = client.post(
        f"/api/v1/goods-receipts/{gr['id']}/post",
        headers=staff_user["auth_headers"],
    )
    assert gr_frozen.status_code == 409
    assert gr_frozen.json()["error"]["code"] == "LOCATION_FROZEN"

    #    - Pengiriman Transfer dari Lokasi X ditolak 409 LOCATION_FROZEN
    ship_frozen = client.post(
        f"/api/v1/stock-transfers/{trf_out['id']}/ship",
        headers=staff_user["auth_headers"],
    )
    assert ship_frozen.status_code == 409
    assert ship_frozen.json()["error"]["code"] == "LOCATION_FROZEN"

    #    - Penerimaan Transfer ke Lokasi X ditolak 409 LOCATION_FROZEN (tetap SHIPPED)
    rec_frozen = client.post(
        f"/api/v1/stock-transfers/{trf_in['id']}/receive",
        headers=staff_user["auth_headers"],
        json={
            "lines": [
                {"line_id": trf_in["lines"][0]["id"], "qty_received": "4"}
            ]
        },
    )
    assert rec_frozen.status_code == 409
    assert rec_frozen.json()["error"]["code"] == "LOCATION_FROZEN"

    # 3. Batalkan Opname #1 (IN_PROGRESS -> CANCELLED) -> pembekuan dilepas, pengiriman trf_out berhasil!
    cancel_opn1 = client.post(
        f"/api/v1/stock-opnames/{opn1['id']}/cancel",
        headers=manager_user["auth_headers"],
    )
    assert cancel_opn1.status_code == 200
    assert cancel_opn1.json()["status"] == "CANCELLED"

    ship_unfrozen = client.post(
        f"/api/v1/stock-transfers/{trf_out['id']}/ship",
        headers=staff_user["auth_headers"],
    )
    assert ship_unfrozen.status_code == 200
    assert ship_unfrozen.json()["status"] == "SHIPPED"

    # 4. Mulai Opname `opn_dup` dan selesaikan hingga COMPLETED -> pastikan pembekuan dilepas setelah COMPLETED
    start_opn2 = client.post(
        f"/api/v1/stock-opnames/{opn_dup['id']}/start",
        headers=manager_user["auth_headers"],
    ).json()
    assert start_opn2["status"] == "IN_PROGRESS"

    # Saat WAITING_APPROVAL pun Lokasi X tetap dibekukan
    client.post(
        f"/api/v1/stock-opnames/{opn_dup['id']}/count",
        headers=staff_user["auth_headers"],
        json={
            "lines": [
                {
                    "line_id": start_opn2["lines"][0]["id"],
                    "qty_physical": start_opn2["lines"][0]["qty_system"],
                }
            ]
        },
    )
    client.post(
        f"/api/v1/stock-opnames/{opn_dup['id']}/submit",
        headers=staff_user["auth_headers"],
    )
    gr_still_frozen = client.post(
        f"/api/v1/goods-receipts/{gr['id']}/post",
        headers=staff_user["auth_headers"],
    )
    assert gr_still_frozen.status_code == 409
    assert gr_still_frozen.json()["error"]["code"] == "LOCATION_FROZEN"

    # Setujui Opname menjadi COMPLETED -> pembekuan dilepas
    approve_opn2 = client.post(
        f"/api/v1/stock-opnames/{opn_dup['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    assert approve_opn2.status_code == 200
    assert approve_opn2.json()["status"] == "COMPLETED"

    # Sekarang posting GR dan penerimaan Transfer ke Lokasi X berhasil (200 OK)!
    gr_post_ok = client.post(
        f"/api/v1/goods-receipts/{gr['id']}/post",
        headers=staff_user["auth_headers"],
    )
    assert gr_post_ok.status_code == 200
    assert gr_post_ok.json()["status"] == "POSTED"

    rec_ok = client.post(
        f"/api/v1/stock-transfers/{trf_in['id']}/receive",
        headers=staff_user["auth_headers"],
        json={
            "lines": [
                {"line_id": trf_in["lines"][0]["id"], "qty_received": "4"}
            ]
        },
    )
    assert rec_ok.status_code == 200
    assert rec_ok.json()["status"] == "RECEIVED"

    # Uji juga endpoint GET /api/v1/stock-opnames
    list_opn = client.get(
        f"/api/v1/stock-opnames?warehouse_id={wh_a['id']}",
        headers=staff_user["auth_headers"],
    ).json()
    assert list_opn["total"] == 2

