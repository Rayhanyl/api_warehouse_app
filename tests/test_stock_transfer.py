"""Pengujian Stock Transfer (FR-06, PRD 5.1, 6.1, 6.3, 6.5, 6.7, AC-02, AC-03, AC-06, AC-09, AC-12)."""

from __future__ import annotations

from decimal import Decimal
import threading
from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection

from app.main import create_app
from app.services import inventory_service
from tests import factories


def _seed_initial_stock(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int,
    item_id: int,
    qty: Decimal,
    actor_id: int,
    ref_id: int = 1,
) -> None:
    """Mengisi saldo awal pengujian melalui pintu resmi inventory_service.apply_movement."""
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
            notes="Seed saldo awal pengujian Transfer",
        )


def test_ac02_negative_stock_prevention_and_allow_negative_stock_flag(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-02 (Pencegahan Stok Negatif, PRD 6.1):
    - Given saldo Barang Y di Gudang A (Lokasi A1) = 10 unit, allow_negative_stock = FALSE,
      dan Transfer 12 unit dari Gudang A berstatus APPROVED.
    - When pengguna mengubah status Transfer menjadi SHIPPED,
    - Then sistem membatalkan transaksi, mengembalikan 409 INSUFFICIENT_STOCK,
      saldo stok tetap 10 unit, tidak ada baris OUT_TRANSFER baru, dan status Transfer tetap APPROVED.
    - Ketika allow_negative_stock pada Gudang A diubah menjadi TRUE oleh Super Admin,
      pengiriman 12 unit berhasil dan saldo menjadi -2.0000.
    """
    wh_a = factories.create_warehouse(
        db_conn, code="WH-AC02-A", name="Gudang A", allow_negative_stock=False
    )
    wh_b = factories.create_warehouse(
        db_conn, code="WH-AC02-B", name="Gudang B", allow_negative_stock=False
    )
    loc_a1 = factories.create_location(
        db_conn, warehouse_id=wh_a["id"], code="A1", name="Rak A1"
    )
    loc_b1 = factories.create_location(
        db_conn, warehouse_id=wh_b["id"], code="B1", name="Rak B1"
    )
    cat = factories.create_category(db_conn, name="Logam")
    uom = factories.create_uom(db_conn, code="PCS-02", name="Pieces", allow_decimal=False)
    item_y = factories.create_item(
        db_conn, sku="BRG-Y", name="Barang Y", category_id=cat["id"], uom_id=uom["id"]
    )

    # Tugaskan manager_user dan staff_user ke Gudang A & B
    for usr in (manager_user, staff_user):
        client.put(
            f"/api/v1/users/{usr['id']}/warehouses",
            headers=superadmin_user["auth_headers"],
            json={"warehouse_ids": [wh_a["id"], wh_b["id"]]},
        )

    # Seed saldo 10 unit di Gudang A Lokasi A1
    _seed_initial_stock(
        db_conn,
        warehouse_id=wh_a["id"],
        location_id=loc_a1["id"],
        item_id=item_y["id"],
        qty=Decimal("10.0000"),
        actor_id=superadmin_user["id"],
    )

    # Buat Transfer 12 unit (DRAFT) lalu setujui (APPROVED)
    trf = client.post(
        "/api/v1/stock-transfers",
        headers=staff_user["auth_headers"],
        json={
            "source_warehouse_id": wh_a["id"],
            "source_location_id": loc_a1["id"],
            "destination_warehouse_id": wh_b["id"],
            "destination_location_id": loc_b1["id"],
            "notes": "Uji AC-02 stok negatif",
            "lines": [{"item_id": item_y["id"], "qty": "12"}],
        },
    ).json()

    approve_res = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # Coba kirim (SHIPPED) -> ditolak 409 INSUFFICIENT_STOCK
    ship_fail = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/ship",
        headers=staff_user["auth_headers"],
    )
    assert ship_fail.status_code == 409
    err = ship_fail.json()["error"]
    assert err["code"] == "INSUFFICIENT_STOCK"
    assert err["details"]["qty_available"] == "10.0000"
    assert err["details"]["qty_requested"] == "12.0000"

    # Pastikan status Transfer tetap APPROVED dan saldo tetap 10.0000
    trf_after = client.get(
        f"/api/v1/stock-transfers/{trf['id']}",
        headers=staff_user["auth_headers"],
    ).json()
    assert trf_after["status"] == "APPROVED"

    bal = db_conn.execute(
        "SELECT qty_on_hand FROM inventory_balances WHERE warehouse_id = %s AND location_id = %s AND item_id = %s",
        (wh_a["id"], loc_a1["id"], item_y["id"]),
    ).fetchone()
    assert bal is not None
    assert bal["qty_on_hand"] == Decimal("10.0000")

    out_mv = db_conn.execute(
        "SELECT COUNT(*)::int AS cnt FROM stock_movements WHERE reference_type = 'STOCK_TRANSFER' AND reference_id = %s",
        (trf["id"],),
    ).fetchone()
    assert out_mv is not None
    assert out_mv["cnt"] == 0

    # Aktifkan allow_negative_stock = TRUE pada Gudang A oleh Super Admin (PRD 6.1)
    patch_wh = client.patch(
        f"/api/v1/warehouses/{wh_a['id']}",
        headers=superadmin_user["auth_headers"],
        json={"allow_negative_stock": True},
    )
    assert patch_wh.status_code == 200

    # Sekarang pengiriman 12 unit berhasil -> saldo menjadi -2.0000
    ship_ok = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/ship",
        headers=staff_user["auth_headers"],
    )
    assert ship_ok.status_code == 200
    assert ship_ok.json()["status"] == "SHIPPED"

    bal_after = db_conn.execute(
        "SELECT qty_on_hand FROM inventory_balances WHERE warehouse_id = %s AND location_id = %s AND item_id = %s",
        (wh_a["id"], loc_a1["id"], item_y["id"]),
    ).fetchone()
    assert bal_after is not None
    assert bal_after["qty_on_hand"] == Decimal("-2.0000")


def test_ac03_inter_warehouse_transfer_consistency_in_transit_and_scoping(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-03 & AC-12 (Konsistensi Transfer Antar-Gudang, In-Transit, dan Warehouse Scoping):
    - Given Transfer Stok 15 unit dari Gudang A ke Gudang B berstatus APPROVED,
    - When status diubah menjadi SHIPPED:
      * Stok Gudang A berkurang 15 unit
      * Tercatat 1 baris OUT_TRANSFER di stock_movements (qty_change = -15)
      * Stok Gudang B belum bertambah (qty_on_hand = 0), namun qty_in_transit menuju Gudang B = 15.
    - When status diubah menjadi RECEIVED dengan qty_received = 15:
      * Stok Gudang B bertambah 15 unit dan qty_in_transit kembali menjadi 0
      * Tercatat 1 baris IN_TRANSFER di stock_movements (qty_change = +15).
    - Mencakup juga validasi asal != tujuan (PRD 6.3), revisi/pembatalan DRAFT & APPROVED,
      serta Warehouse Scoping (PRD 3.2 poin 3 & 5).
    """
    wh_a = factories.create_warehouse(db_conn, code="WH-AC03-A", name="Gudang Asal A")
    wh_b = factories.create_warehouse(db_conn, code="WH-AC03-B", name="Gudang Tujuan B")
    wh_c = factories.create_warehouse(db_conn, code="WH-AC03-C", name="Gudang Lain C")
    loc_a1 = factories.create_location(
        db_conn, warehouse_id=wh_a["id"], code="LOC-A1", name="Lokasi A1"
    )
    loc_b1 = factories.create_location(
        db_conn, warehouse_id=wh_b["id"], code="LOC-B1", name="Lokasi B1"
    )
    loc_c1 = factories.create_location(
        db_conn, warehouse_id=wh_c["id"], code="LOC-C1", name="Lokasi C1"
    )
    cat = factories.create_category(db_conn, name="Otomotif")
    uom = factories.create_uom(db_conn, code="PCS-03", name="Pieces", allow_decimal=False)
    item = factories.create_item(
        db_conn, sku="OT-015", name="Filter Oli", category_id=cat["id"], uom_id=uom["id"]
    )

    staff_b = factories.create_user(
        db_conn,
        username="staff_wh_b",
        email="staff_b@wms.test",
        role_name="Warehouse Staff",
        warehouse_ids=[wh_b["id"]],
    )
    staff_c = factories.create_user(
        db_conn,
        username="staff_wh_c",
        email="staff_c@wms.test",
        role_name="Warehouse Staff",
        warehouse_ids=[wh_c["id"]],
    )

    # Tugaskan staff_user ke Gudang A saja, dan manager_user ke Gudang A
    client.put(
        f"/api/v1/users/{staff_user['id']}/warehouses",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_ids": [wh_a["id"]]},
    )
    client.put(
        f"/api/v1/users/{manager_user['id']}/warehouses",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_ids": [wh_a["id"]]},
    )

    # Seed stok awal 20 unit di Gudang A (loc_a1)
    _seed_initial_stock(
        db_conn,
        warehouse_id=wh_a["id"],
        location_id=loc_a1["id"],
        item_id=item["id"],
        qty=Decimal("20.0000"),
        actor_id=superadmin_user["id"],
    )

    # 1. Validasi PRD 6.3: asal == tujuan ditolak 422 VALIDATION_ERROR
    same_src_dst = client.post(
        "/api/v1/stock-transfers",
        headers=staff_user["auth_headers"],
        json={
            "source_warehouse_id": wh_a["id"],
            "source_location_id": loc_a1["id"],
            "destination_warehouse_id": wh_a["id"],
            "destination_location_id": loc_a1["id"],
            "lines": [{"item_id": item["id"], "qty": "5"}],
        },
    )
    assert same_src_dst.status_code == 422
    assert same_src_dst.json()["error"]["code"] == "VALIDATION_ERROR"

    # 2. AC-12: staff_b (hanya ditugaskan ke Gudang B) mencoba membuat Transfer dari Gudang A -> 403 WAREHOUSE_NOT_ASSIGNED
    unassigned_create = client.post(
        "/api/v1/stock-transfers",
        headers=staff_b["auth_headers"],
        json={
            "source_warehouse_id": wh_a["id"],
            "source_location_id": loc_a1["id"],
            "destination_warehouse_id": wh_b["id"],
            "destination_location_id": loc_b1["id"],
            "lines": [{"item_id": item["id"], "qty": "5"}],
        },
    )
    assert unassigned_create.status_code == 403
    assert unassigned_create.json()["error"]["code"] == "WAREHOUSE_NOT_ASSIGNED"

    # 3. Buat Transfer oleh staff_user (Gudang A) awalnya 10 unit, lalu PATCH menjadi 15 unit
    create_res = client.post(
        "/api/v1/stock-transfers",
        headers=staff_user["auth_headers"],
        json={
            "source_warehouse_id": wh_a["id"],
            "source_location_id": loc_a1["id"],
            "destination_warehouse_id": wh_b["id"],
            "destination_location_id": loc_b1["id"],
            "notes": "Transfer ke Gudang B",
            "lines": [{"item_id": item["id"], "qty": "10"}],
        },
    )
    assert create_res.status_code == 201
    trf = create_res.json()
    assert trf["status"] == "DRAFT"
    assert trf["transfer_number"].startswith("TRF-")

    patch_res = client.patch(
        f"/api/v1/stock-transfers/{trf['id']}",
        headers=staff_user["auth_headers"],
        json={
            "notes": "Revisi qty menjadi 15 unit",
            "lines": [{"item_id": item["id"], "qty": "15"}],
        },
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["lines"][0]["qty"] == "15.0000"

    # Warehouse Staff Gudang C tidak boleh membaca Transfer A->B (PRD 3.2 poin 5)
    forbid_read_c = client.get(
        f"/api/v1/stock-transfers/{trf['id']}",
        headers=staff_c["auth_headers"],
    )
    assert forbid_read_c.status_code == 403
    assert forbid_read_c.json()["error"]["code"] == "WAREHOUSE_NOT_ASSIGNED"

    # Sedangkan staff_b (ditugaskan ke Gudang B = tujuan) BOLEH melihat Transfer A->B
    allow_read_b = client.get(
        f"/api/v1/stock-transfers/{trf['id']}",
        headers=staff_b["auth_headers"],
    )
    assert allow_read_b.status_code == 200

    # 4. Setujui Transfer oleh Warehouse Manager Gudang A (DRAFT -> APPROVED)
    approve_res = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # Warehouse Staff tidak boleh membatalkan Transfer yang sudah APPROVED (butuh transfer:approve)
    staff_cancel_approved = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/cancel",
        headers=staff_user["auth_headers"],
    )
    assert staff_cancel_approved.status_code == 403
    assert staff_cancel_approved.json()["error"]["code"] == "PERMISSION_DENIED"

    # 5. Kirim Transfer oleh staff_user Gudang A (APPROVED -> SHIPPED)
    ship_res = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/ship",
        headers=staff_user["auth_headers"],
    )
    assert ship_res.status_code == 200
    shipped = ship_res.json()
    assert shipped["status"] == "SHIPPED"
    assert shipped["shipped_by"] == staff_user["id"]

    # Verifikasi AC-03 saat SHIPPED:
    # - Saldo Gudang A berkurang 15 (20 - 15 = 5.0000)
    # - Saldo Gudang B belum bertambah (masih 0.0000), tetapi qty_in_transit di Gudang B = 15.0000
    # - Tercatat tepat 1 baris OUT_TRANSFER di stock_movements
    stock_a = client.get(
        f"/api/v1/stock/by-location?warehouse_id={wh_a['id']}&location_id={loc_a1['id']}&item_id={item['id']}",
        headers=superadmin_user["auth_headers"],
    ).json()
    assert stock_a["items"][0]["qty_on_hand"] == "5.0000"

    stock_b_in_transit = client.get(
        f"/api/v1/stock/by-location?warehouse_id={wh_b['id']}&location_id={loc_b1['id']}&item_id={item['id']}",
        headers=superadmin_user["auth_headers"],
    ).json()
    assert len(stock_b_in_transit["items"]) == 1
    assert stock_b_in_transit["items"][0]["qty_on_hand"] == "0.0000"
    assert stock_b_in_transit["items"][0]["qty_in_transit"] == "15.0000"

    movements_ship = client.get(
        f"/api/v1/stock/movements?reference_type=STOCK_TRANSFER&reference_id={trf['id']}",
        headers=superadmin_user["auth_headers"],
    ).json()
    assert movements_ship["total"] == 1
    mv_out = movements_ship["items"][0]
    assert mv_out["movement_type"] == "OUT_TRANSFER"
    assert mv_out["warehouse_id"] == wh_a["id"]
    assert mv_out["qty_before"] == "20.0000"
    assert mv_out["qty_change"] == "-15.0000"
    assert mv_out["qty_after"] == "5.0000"

    # AC-12: staff_user (hanya ditugaskan ke Gudang A) ditolak saat mencoba menerima di Gudang B
    receive_wrong_wh = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/receive",
        headers=staff_user["auth_headers"],
        json={
            "lines": [
                {"line_id": shipped["lines"][0]["id"], "qty_received": "15"}
            ]
        },
    )
    assert receive_wrong_wh.status_code == 403
    assert receive_wrong_wh.json()["error"]["code"] == "WAREHOUSE_NOT_ASSIGNED"

    # 6. Terima Transfer di Gudang B oleh staff_b dengan qty_received = 15 (SHIPPED -> RECEIVED)
    receive_res = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/receive",
        headers=staff_b["auth_headers"],
        json={
            "lines": [
                {"line_id": shipped["lines"][0]["id"], "qty_received": "15"}
            ]
        },
    )
    assert receive_res.status_code == 200
    received = receive_res.json()
    assert received["status"] == "RECEIVED"
    assert received["received_by"] == staff_b["id"]
    assert received["lines"][0]["qty_received"] == "15.0000"
    assert received["lines"][0]["qty_variance"] == "0.0000"

    # Verifikasi AC-03 setelah RECEIVED:
    # - Stok Gudang B bertambah menjadi 15.0000 dan qty_in_transit menjadi 0.0000
    # - Tercatat 1 baris IN_TRANSFER di stock_movements
    stock_b_after = client.get(
        f"/api/v1/stock/by-location?warehouse_id={wh_b['id']}&location_id={loc_b1['id']}&item_id={item['id']}",
        headers=superadmin_user["auth_headers"],
    ).json()
    assert stock_b_after["items"][0]["qty_on_hand"] == "15.0000"
    assert stock_b_after["items"][0]["qty_in_transit"] == "0.0000"

    movements_all = client.get(
        f"/api/v1/stock/movements?reference_type=STOCK_TRANSFER&reference_id={trf['id']}",
        headers=superadmin_user["auth_headers"],
    ).json()
    assert movements_all["total"] == 2
    in_mv = next(m for m in movements_all["items"] if m["movement_type"] == "IN_TRANSFER")
    assert in_mv["warehouse_id"] == wh_b["id"]
    assert in_mv["qty_before"] == "0.0000"
    assert in_mv["qty_change"] == "15.0000"
    assert in_mv["qty_after"] == "15.0000"

    # 7. Uji pembatalan Transfer DRAFT (oleh staff_user) dan daftar Transfer (GET /api/v1/stock-transfers)
    trf_draft_cancel = client.post(
        "/api/v1/stock-transfers",
        headers=staff_user["auth_headers"],
        json={
            "source_warehouse_id": wh_a["id"],
            "source_location_id": loc_a1["id"],
            "destination_warehouse_id": wh_b["id"],
            "destination_location_id": loc_b1["id"],
            "lines": [{"item_id": item["id"], "qty": "2"}],
        },
    ).json()
    cancel_ok = client.post(
        f"/api/v1/stock-transfers/{trf_draft_cancel['id']}/cancel",
        headers=staff_user["auth_headers"],
    )
    assert cancel_ok.status_code == 200
    assert cancel_ok.json()["status"] == "CANCELLED"

    list_b = client.get(
        f"/api/v1/stock-transfers?destination_warehouse_id={wh_b['id']}",
        headers=staff_b["auth_headers"],
    ).json()
    assert list_b["total"] == 2

    list_c = client.get(
        "/api/v1/stock-transfers",
        headers=staff_c["auth_headers"],
    ).json()
    assert list_c["total"] == 0


def test_ac06_concurrent_ship_only_one_succeeds(
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-06 (Konkurensi Pengiriman):
    - Given saldo Barang Y di Lokasi A1 adalah 10 unit dengan allow_negative_stock = FALSE,
      dan dua Transfer berbeda masing-masing 8 unit dari Lokasi A1 berstatus APPROVED,
    - When kedua Transfer diubah menjadi SHIPPED secara bersamaan oleh 2 thread,
    - Then tepat satu berhasil (200 OK) dan satu ditolak dengan 409 INSUFFICIENT_STOCK,
      saldo akhir 2 unit, dan hanya ada 1 baris OUT_TRANSFER.
    """
    app = create_app()
    with TestClient(app) as main_client:
        wh_a = factories.create_warehouse(
            db_conn, code="WH-AC06-A", name="Gudang Konkuren A", allow_negative_stock=False
        )
        wh_b = factories.create_warehouse(
            db_conn, code="WH-AC06-B", name="Gudang Konkuren B", allow_negative_stock=False
        )
        loc_a1 = factories.create_location(
            db_conn, warehouse_id=wh_a["id"], code="LOC-06-A1", name="Lokasi A1"
        )
        loc_b1 = factories.create_location(
            db_conn, warehouse_id=wh_b["id"], code="LOC-06-B1", name="Lokasi B1"
        )
        cat = factories.create_category(db_conn, name="Konkurensi Transfer")
        uom = factories.create_uom(db_conn, code="PCS-06", name="Pieces", allow_decimal=False)
        item_y = factories.create_item(
            db_conn, sku="SKU-AC06", name="Barang Y Konkuren", category_id=cat["id"], uom_id=uom["id"]
        )

        for usr in (manager_user, staff_user):
            main_client.put(
                f"/api/v1/users/{usr['id']}/warehouses",
                headers=superadmin_user["auth_headers"],
                json={"warehouse_ids": [wh_a["id"], wh_b["id"]]},
            )

        # Seed saldo 10 unit di Lokasi A1
        _seed_initial_stock(
            db_conn,
            warehouse_id=wh_a["id"],
            location_id=loc_a1["id"],
            item_id=item_y["id"],
            qty=Decimal("10.0000"),
            actor_id=superadmin_user["id"],
        )

        # Buat 2 Transfer masing-masing 8 unit dan setujui keduanya menjadi APPROVED
        transfer_ids: list[int] = []
        for idx in (1, 2):
            trf = main_client.post(
                "/api/v1/stock-transfers",
                headers=staff_user["auth_headers"],
                json={
                    "source_warehouse_id": wh_a["id"],
                    "source_location_id": loc_a1["id"],
                    "destination_warehouse_id": wh_b["id"],
                    "destination_location_id": loc_b1["id"],
                    "notes": f"Transfer konkuren #{idx}",
                    "lines": [{"item_id": item_y["id"], "qty": "8"}],
                },
            ).json()
            app_res = main_client.post(
                f"/api/v1/stock-transfers/{trf['id']}/approve",
                headers=manager_user["auth_headers"],
            )
            assert app_res.status_code == 200
            transfer_ids.append(int(trf["id"]))

        barrier = threading.Barrier(2)
        results: list[tuple[int, dict[str, Any]]] = []
        lock = threading.Lock()

        def worker(tid: int) -> None:
            with TestClient(app) as thread_client:
                barrier.wait()
                resp = thread_client.post(
                    f"/api/v1/stock-transfers/{tid}/ship",
                    headers=staff_user["auth_headers"],
                )
                with lock:
                    results.append((resp.status_code, resp.json()))

        t1 = threading.Thread(target=worker, args=(transfer_ids[0],))
        t2 = threading.Thread(target=worker, args=(transfer_ids[1],))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        status_codes = sorted(r[0] for r in results)
        assert status_codes == [200, 409]

        failed_body = next(r[1] for r in results if r[0] == 409)
        assert failed_body["error"]["code"] == "INSUFFICIENT_STOCK"

        # Verifikasi saldo akhir Lokasi A1 adalah 2.0000 unit
        bal = db_conn.execute(
            "SELECT qty_on_hand FROM inventory_balances WHERE warehouse_id = %s AND location_id = %s AND item_id = %s",
            (wh_a["id"], loc_a1["id"], item_y["id"]),
        ).fetchone()
        assert bal is not None
        assert bal["qty_on_hand"] == Decimal("2.0000")

        # Verifikasi hanya ada tepat 1 baris OUT_TRANSFER di stock_movements
        mv_count = db_conn.execute(
            "SELECT COUNT(*)::int AS cnt FROM stock_movements WHERE movement_type = 'OUT_TRANSFER' AND warehouse_id = %s",
            (wh_a["id"],),
        ).fetchone()
        assert mv_count is not None
        assert mv_count["cnt"] == 1


def test_ac09_transfer_receipt_variance_validation_and_accounting(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-09 (Selisih Penerimaan Transfer, PRD 6.7):
    - Given Transfer 25 unit berstatus SHIPPED,
    - When penerimaan diisi qty_received = 26 -> ditolak 409 TRANSFER_QTY_EXCEEDS_SHIPPED.
    - When penerimaan diisi qty_received = 23 tanpa alasan selisih -> ditolak 422 VALIDATION_ERROR.
    - When diisi qty_received = 23 dengan alasan selisih:
      * Stok tujuan bertambah 23 unit (bukan 25)
      * Tercatat 1 baris IN_TRANSFER sebesar 23
      * Selisih 2 beserta variance_reason tersimpan pada baris Transfer
      * Selisih 2 tidak dikembalikan ke gudang asal dan tidak menghasilkan baris ledger tambahan.
    """
    wh_a = factories.create_warehouse(db_conn, code="WH-AC09-A", name="Gudang Asal 09")
    wh_b = factories.create_warehouse(db_conn, code="WH-AC09-B", name="Gudang Tujuan 09")
    loc_a1 = factories.create_location(
        db_conn, warehouse_id=wh_a["id"], code="A1-09", name="Rak A1"
    )
    loc_b1 = factories.create_location(
        db_conn, warehouse_id=wh_b["id"], code="B1-09", name="Rak B1"
    )
    cat = factories.create_category(db_conn, name="Kaca")
    uom = factories.create_uom(db_conn, code="PCS-09", name="Pieces", allow_decimal=False)
    item = factories.create_item(
        db_conn, sku="KC-025", name="Bohlam Lampu", category_id=cat["id"], uom_id=uom["id"]
    )

    for usr in (manager_user, staff_user):
        client.put(
            f"/api/v1/users/{usr['id']}/warehouses",
            headers=superadmin_user["auth_headers"],
            json={"warehouse_ids": [wh_a["id"], wh_b["id"]]},
        )

    # Seed 30 unit di Gudang A Lokasi A1
    _seed_initial_stock(
        db_conn,
        warehouse_id=wh_a["id"],
        location_id=loc_a1["id"],
        item_id=item["id"],
        qty=Decimal("30.0000"),
        actor_id=superadmin_user["id"],
    )

    # Buat, setujui, dan kirim Transfer 25 unit (sehingga saldo Gudang A tersisa 5 unit)
    trf = client.post(
        "/api/v1/stock-transfers",
        headers=staff_user["auth_headers"],
        json={
            "source_warehouse_id": wh_a["id"],
            "source_location_id": loc_a1["id"],
            "destination_warehouse_id": wh_b["id"],
            "destination_location_id": loc_b1["id"],
            "lines": [{"item_id": item["id"], "qty": "25"}],
        },
    ).json()
    line_id = trf["lines"][0]["id"]

    client.post(
        f"/api/v1/stock-transfers/{trf['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    client.post(
        f"/api/v1/stock-transfers/{trf['id']}/ship",
        headers=staff_user["auth_headers"],
    )

    # 1. Coba terima dengan qty_received = 26 (> 25) -> 409 TRANSFER_QTY_EXCEEDS_SHIPPED
    exceed_res = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/receive",
        headers=staff_user["auth_headers"],
        json={"lines": [{"line_id": line_id, "qty_received": "26"}]},
    )
    assert exceed_res.status_code == 409
    assert exceed_res.json()["error"]["code"] == "TRANSFER_QTY_EXCEEDS_SHIPPED"

    # 2. Coba terima dengan qty_received = 23 tanpa variance_reason -> 422 VALIDATION_ERROR
    no_reason_res = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/receive",
        headers=staff_user["auth_headers"],
        json={"lines": [{"line_id": line_id, "qty_received": "23", "variance_reason": "   "}]},
    )
    assert no_reason_res.status_code == 422
    assert no_reason_res.json()["error"]["code"] == "VALIDATION_ERROR"

    # 3. Terima dengan qty_received = 23 dan alasan selisih yang sah -> 200 OK
    receive_ok = client.post(
        f"/api/v1/stock-transfers/{trf['id']}/receive",
        headers=staff_user["auth_headers"],
        json={
            "lines": [
                {
                    "line_id": line_id,
                    "qty_received": "23",
                    "variance_reason": "2 unit pecah saat pengiriman ekspedisi",
                }
            ]
        },
    )
    assert receive_ok.status_code == 200
    rec_data = receive_ok.json()
    assert rec_data["status"] == "RECEIVED"
    rec_line = rec_data["lines"][0]
    assert rec_line["qty"] == "25.0000"
    assert rec_line["qty_received"] == "23.0000"
    assert rec_line["qty_variance"] == "2.0000"
    assert rec_line["variance_reason"] == "2 unit pecah saat pengiriman ekspedisi"

    # Verifikasi stok tujuan bertambah 23 unit, dan stok asal tetap 5 unit (selisih 2 tidak kembali ke asal)
    bal_b = db_conn.execute(
        "SELECT qty_on_hand FROM inventory_balances WHERE warehouse_id = %s AND location_id = %s AND item_id = %s",
        (wh_b["id"], loc_b1["id"], item["id"]),
    ).fetchone()
    assert bal_b is not None
    assert bal_b["qty_on_hand"] == Decimal("23.0000")

    bal_a = db_conn.execute(
        "SELECT qty_on_hand FROM inventory_balances WHERE warehouse_id = %s AND location_id = %s AND item_id = %s",
        (wh_a["id"], loc_a1["id"], item["id"]),
    ).fetchone()
    assert bal_a is not None
    assert bal_a["qty_on_hand"] == Decimal("5.0000")

    # Verifikasi ledger hanya memiliki 2 baris untuk Transfer ini (1 OUT_TRANSFER -25, 1 IN_TRANSFER +23)
    mvs = client.get(
        f"/api/v1/stock/movements?reference_type=STOCK_TRANSFER&reference_id={trf['id']}",
        headers=superadmin_user["auth_headers"],
    ).json()
    assert mvs["total"] == 2
    in_mv = next(m for m in mvs["items"] if m["movement_type"] == "IN_TRANSFER")
    assert in_mv["qty_change"] == "23.0000"
    assert in_mv["qty_after"] == "23.0000"

