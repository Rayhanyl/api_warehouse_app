"""Pengujian terfokus untuk Kriteria Penerimaan AC-15 s.d. AC-22 (PRD 10.1 & AGENTS.md §8).

AC-15: Penomoran Dokumen Unik & Konkuren (next_number, rollover, locking)
AC-16: Paginasi, Whitelist Pengurutan, dan Format Serialisasi Desimal NUMERIC(18,4)
AC-17: Korelasi Request ID, Keamanan Karakter X-Request-ID, dan Pemeriksaan Kesehatan (/health)
AC-18: Runner Migrasi Forward-Only, Pencatatan schema_migrations, dan Idempotensi
AC-19: Imutabilitas Data Master (SKU, allow_decimal UoM, penonaktifan entitas aktif)
AC-20: Validasi Kepemilikan Lokasi Gudang dan Audit Perubahan allow_negative_stock
AC-21: Penolakan Transisi Status Dokumen di Luar State Machine (FSM)
AC-22: Kelengkapan Audit Log, Sanitasi Rahasia/Password, dan Warehouse Scoping Audit
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import threading
from typing import Any

from fastapi.testclient import TestClient
import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from app.core.exceptions import (
    EntityInUse,
    InvalidLocationError,
    InvalidStateTransition,
    ValidationDomainError,
)
from app.services import (
    inventory_service,
    numbering_service,
    warehouse_service,
)
from db import migrate
from tests import factories


def test_ac15_document_numbering_concurrency_and_rollover(
    db_conn: Connection[dict[str, Any]],
    setup_test_database: str,
) -> None:
    """AC-15: Penomoran Dokumen (next_number).
    - Format {PREFIX}-{YYYYMM}-{NNNN}.
    - Penguncian baris sequence memastikan tidak ada duplikasi nomor saat digenerate oleh thread konkuren.
    - Rollover: Saat periode berubah ke bulan baru, nomor sequence reset kembali ke 0001.
    """
    period_curr = date(2026, 10, 15)
    period_next = date(2026, 11, 1)

    # 1. Konkurensi generasi nomor PO oleh 10 worker paralel
    num_workers = 10
    barrier = threading.Barrier(num_workers)

    def _generate_po(worker_id: int) -> str:
        with psycopg.connect(setup_test_database, autocommit=True, row_factory=dict_row) as conn:
            barrier.wait(timeout=5)
            with conn.transaction():
                return numbering_service.next_number(conn, "PO", reference_date=period_curr)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        generated_numbers = list(executor.map(_generate_po, range(num_workers)))

    # Verifikasi seluruh 10 nomor unik dan berurutan dari PO-202610-0001 s.d. PO-202610-0010
    assert len(generated_numbers) == num_workers
    assert len(set(generated_numbers)) == num_workers
    expected_sequence = [f"PO-202610-{i:04d}" for i in range(1, num_workers + 1)]
    assert sorted(generated_numbers) == expected_sequence

    # 2. Uji rollover: pada periode bulan berikutnya (2026-11), sequence reset kembali ke 0001
    with db_conn.transaction():
        next_month_num = numbering_service.next_number(db_conn, "PO", reference_date=period_next)
    assert next_month_num == "PO-202611-0001"

    # 3. Tipe dokumen tidak dikenal ditolak ValidationDomainError
    try:
        with db_conn.transaction():
            numbering_service.next_number(db_conn, "UNKNOWN_DOC")
        raise AssertionError("Seharusnya menolak tipe dokumen tidak dikenal")
    except ValidationDomainError as exc:
        assert exc.code == "VALIDATION_ERROR"


def test_ac16_pagination_sorting_whitelist_and_decimal_formatting(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
) -> None:
    """AC-16: Paginasi, Whitelist Pengurutan, dan Format Serialisasi Desimal.
    - limit default 50, batas maksimal 200, offset minimal 0 (diluar batas -> 422).
    - Sort whitelist menolak kolom ilegal / injeksi SQL (-> 422).
    - Kuantitas pada respons JSON diserialisasi sebagai string desimal 4 digit (NUMERIC(18,4)).
    """
    cat = factories.create_category(db_conn, name="Paginasi Cat")
    uom = factories.create_uom(db_conn, code="PCS-PG", name="Pieces", allow_decimal=False)

    # Buat beberapa item untuk uji sort & paginasi
    for i in range(1, 6):
        factories.create_item(
            db_conn,
            sku=f"PG-ITEM-{i:02d}",
            name=f"Barang Paginasi {i}",
            category_id=cat["id"],
            uom_id=uom["id"],
        )

    # 1. Batas paginasi: offset < 0 -> 422, limit > 200 -> 422, limit < 1 -> 422
    assert client.get("/api/v1/items?offset=-1", headers=superadmin_user["auth_headers"]).status_code == 422
    assert client.get("/api/v1/items?limit=201", headers=superadmin_user["auth_headers"]).status_code == 422
    assert client.get("/api/v1/items?limit=0", headers=superadmin_user["auth_headers"]).status_code == 422

    # 2. Paginasi valid
    res_p1 = client.get("/api/v1/items?limit=2&offset=0", headers=superadmin_user["auth_headers"])
    assert res_p1.status_code == 200
    p1_data = res_p1.json()
    assert p1_data["limit"] == 2
    assert p1_data["offset"] == 0
    assert len(p1_data["items"]) == 2

    # 3. Sort whitelist: kolom valid berhasil, kolom ilegal / SQL injection ditolak 422
    sort_ok = client.get(
        "/api/v1/items?sort_by=sku&sort_dir=asc",
        headers=superadmin_user["auth_headers"],
    )
    assert sort_ok.status_code == 200

    sort_bad = client.get(
        "/api/v1/items?sort_by=non_existent_column&sort_dir=asc",
        headers=superadmin_user["auth_headers"],
    )
    assert sort_bad.status_code == 422
    assert sort_bad.json()["error"]["code"] == "VALIDATION_ERROR"

    sort_inject = client.get(
        "/api/v1/items?sort_by=sku;DROP+TABLE+items--&sort_dir=asc",
        headers=superadmin_user["auth_headers"],
    )
    assert sort_inject.status_code == 422

    # 4. Format desimal string: periksa respons stok dan pergerakan
    uom_dec = factories.create_uom(db_conn, code="KG-DEC", name="Kilogram", allow_decimal=True)
    wh = factories.create_warehouse(db_conn, code="WH-DEC-TEST", name="Gudang Desimal")
    loc = factories.create_location(db_conn, warehouse_id=wh["id"], code="LOC-DEC", name="Lokasi Desimal")
    item = factories.create_item(db_conn, sku="SKU-DEC-01", name="Barang Desimal", category_id=cat["id"], uom_id=uom_dec["id"])

    with db_conn.transaction():
        inventory_service.apply_movement(
            db_conn,
            movement_type="IN_PURCHASE",
            warehouse_id=wh["id"],
            location_id=loc["id"],
            item_id=item["id"],
            qty_change=Decimal("25.5000"),
            reference_type="GOODS_RECEIPT",
            reference_id=10,
            created_by=superadmin_user["id"],
        )

    bal_res = client.get(
        f"/api/v1/stock/balances?warehouse_id={wh['id']}&location_id={loc['id']}",
        headers=superadmin_user["auth_headers"],
    )
    assert bal_res.status_code == 200
    bal_item = bal_res.json()["items"][0]
    assert bal_item["qty_on_hand"] == "25.5000"
    assert isinstance(bal_item["qty_on_hand"], str)


def test_ac17_request_id_correlation_and_health_check(
    client: TestClient,
    superadmin_user: dict[str, Any],
) -> None:
    """AC-17: Korelasi Request ID, Sanitasi Header, dan Endpoint Health.
    - Header X-Request-ID valid diteruskan kembali di response.
    - Header X-Request-ID tidak aman / invalid diganti dengan UUID baru yang valid.
    - Endpoint GET /health mengembalikan status 'ok' dan database 'connected'.
    """
    # 1. Request ID valid
    safe_req_id = "test-req-12345.abc_XYZ"
    res_safe = client.get(
        "/api/v1/warehouses",
        headers={**superadmin_user["auth_headers"], "X-Request-ID": safe_req_id},
    )
    assert res_safe.status_code == 200
    assert res_safe.headers.get("X-Request-ID") == safe_req_id

    # 2. Request ID berbahaya (mengandung karakter terlarang / panjang > 128)
    malicious_req_id = "bad\r\nHeader-Injection:" + ("A" * 150)
    res_sanitized = client.get(
        "/api/v1/warehouses",
        headers={**superadmin_user["auth_headers"], "X-Request-ID": malicious_req_id},
    )
    assert res_sanitized.status_code == 200
    returned_id = res_sanitized.headers.get("X-Request-ID")
    assert returned_id != malicious_req_id
    assert len(returned_id) == 36  # UUID4 standard length

    # 3. GET /health
    health_res = client.get("/health")
    assert health_res.status_code == 200
    health_body = health_res.json()
    assert health_body["status"] == "ok"
    assert health_body["database"] == "connected"


def test_ac18_migration_runner_forward_only_idempotency(
    db_conn: Connection[dict[str, Any]],
    setup_test_database: str,
) -> None:
    """AC-18: Runner Migrasi SQL Forward-Only & Idempotensi (db.migrate).
    - Membaca berkas migrasi berurutan.
    - Mencatat versi ke tabel schema_migrations.
    - Pemanggilan ulang ketika semua migrasi sudah diterapkan tidak mengeksekusi ulang migrasi apa pun.
    """
    # Verifikasi tabel schema_migrations ada dan memuat versi migrasi
    rows = db_conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    assert len(rows) >= 9
    assert any("001_create_auth_tables" in r["version"] for r in rows)

    # Jalankan run_migrations kembali pada koneksi database test
    applied = migrate.run_migrations(setup_test_database)
    # Karena semua berkas migrasi sudah diterapkan di fixture setup, tidak ada berkas baru yang diaplikasikan
    assert applied == []


def test_ac19_master_data_immutability_and_entity_in_use(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
) -> None:
    """AC-19: Imutabilitas Data Master & Penegakan ENTITY_IN_USE (PRD 5.2.1, 7.5).
    - SKU barang tidak dapat diubah setelah barang tercatat di transaksi / saldo.
    - UoM allow_decimal (TRUE -> FALSE) tidak dapat diubah setelah digunakan oleh barang.
    - Entitas yang sedang memiliki saldo atau transaksi terkait tidak dapat dinonaktifkan (is_active=False).
    """
    wh = factories.create_warehouse(db_conn, code="WH-AC19", name="Gudang AC19")
    loc = factories.create_location(db_conn, warehouse_id=wh["id"], code="LOC-AC19", name="Lokasi AC19")
    cat = factories.create_category(db_conn, name="Kategori AC19")
    uom = factories.create_uom(db_conn, code="MTR-19", name="Meter 19", allow_decimal=True)
    item = factories.create_item(
        db_conn, sku="SKU-IMMUT-01", name="Barang Immut", category_id=cat["id"], uom_id=uom["id"]
    )

    # 1. Ubah allow_decimal (TRUE -> FALSE) pada UoM yang sudah digunakan oleh barang -> 409 ENTITY_IN_USE
    patch_uom = client.patch(
        f"/api/v1/uoms/{uom['id']}",
        headers=purchasing_user["auth_headers"],
        json={"allow_decimal": False},
    )
    assert patch_uom.status_code == 409
    assert patch_uom.json()["error"]["code"] == "ENTITY_IN_USE"

    # Seed stok pada barang ini
    with db_conn.transaction():
        inventory_service.apply_movement(
            db_conn,
            movement_type="IN_PURCHASE",
            warehouse_id=wh["id"],
            location_id=loc["id"],
            item_id=item["id"],
            qty_change=Decimal("10.0000"),
            reference_type="GOODS_RECEIPT",
            reference_id=99,
            created_by=superadmin_user["id"],
        )

    # 2. Coba ubah SKU barang yang sudah bersaldo -> 409 ENTITY_IN_USE
    patch_sku = client.patch(
        f"/api/v1/items/{item['id']}",
        headers=purchasing_user["auth_headers"],
        json={"sku": "SKU-BARU-01"},
    )
    assert patch_sku.status_code == 409
    assert patch_sku.json()["error"]["code"] == "ENTITY_IN_USE"

    # 3. Coba nonaktifkan gudang yang masih memiliki saldo -> 409 ENTITY_IN_USE
    deact_wh = client.patch(
        f"/api/v1/warehouses/{wh['id']}",
        headers=superadmin_user["auth_headers"],
        json={"is_active": False},
    )
    assert deact_wh.status_code == 409
    assert deact_wh.json()["error"]["code"] == "ENTITY_IN_USE"

    # 4. Coba nonaktifkan lokasi yang masih memiliki saldo -> 409 ENTITY_IN_USE
    deact_loc = client.patch(
        f"/api/v1/locations/{loc['id']}",
        headers=superadmin_user["auth_headers"],
        json={"is_active": False},
    )
    assert deact_loc.status_code == 409
    assert deact_loc.json()["error"]["code"] == "ENTITY_IN_USE"


def test_ac20_location_warehouse_ownership_and_negative_stock_audit(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
) -> None:
    """AC-20: Kepemilikan Lokasi Gudang (validate_location) dan Audit Log allow_negative_stock.
    - Lokasi harus milik warehouse terkait; jika tidak cocok -> ditolak INVALID_LOCATION.
    - Perubahan flag allow_negative_stock dicatat lengkap di audit_logs.
    """
    wh_1 = factories.create_warehouse(db_conn, code="WH-20-1", name="Gudang 20-1", allow_negative_stock=False)
    wh_2 = factories.create_warehouse(db_conn, code="WH-20-2", name="Gudang 20-2", allow_negative_stock=False)
    loc_1 = factories.create_location(db_conn, warehouse_id=wh_1["id"], code="LOC-20-1", name="Lokasi 1")
    loc_2 = factories.create_location(db_conn, warehouse_id=wh_2["id"], code="LOC-20-2", name="Lokasi 2")

    # 1. Kontrak validate_location pada warehouse_service
    # Cocok -> lolos
    warehouse_service.validate_location(db_conn, warehouse_id=wh_1["id"], location_id=loc_1["id"])
    warehouse_service.validate_location(db_conn, warehouse_id=wh_2["id"], location_id=loc_2["id"])

    # Tidak cocok -> InvalidLocationError (422)
    try:
        warehouse_service.validate_location(db_conn, warehouse_id=wh_1["id"], location_id=loc_2["id"])
        raise AssertionError("Seharusnya melempar InvalidLocationError karena lokasi milik gudang lain")
    except InvalidLocationError as exc:
        assert exc.code == "INVALID_LOCATION"

    # 2. Update allow_negative_stock menghasilkan audit log
    upd_wh = client.patch(
        f"/api/v1/warehouses/{wh_1['id']}",
        headers=superadmin_user["auth_headers"],
        json={"allow_negative_stock": True},
    )
    assert upd_wh.status_code == 200
    assert upd_wh.json()["allow_negative_stock"] is True

    # Periksa audit log untuk tabel warehouses dan id wh_1
    audit_row = db_conn.execute(
        """
        SELECT * FROM audit_logs
        WHERE entity_type = 'warehouses' AND entity_id = %s AND action = 'WAREHOUSE_UPDATED'
        ORDER BY id DESC LIMIT 1
        """,
        (str(wh_1["id"]),),
    ).fetchone()
    assert audit_row is not None
    assert audit_row["old_values"]["allow_negative_stock"] is False
    assert audit_row["new_values"]["allow_negative_stock"] is True


def test_ac21_invalid_state_transition_documents(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-21: Penolakan Transisi Status Dokumen di Luar FSM (PRD 5.1).
    - Memanggil aksi status yang tidak valid untuk status dokumen saat ini -> 409 INVALID_STATE_TRANSITION.
    """
    wh = factories.create_warehouse(db_conn, code="WH-AC21", name="Gudang FSM")
    loc = factories.create_location(db_conn, warehouse_id=wh["id"], code="LOC-21", name="Lokasi 21")
    sup = factories.create_supplier(db_conn, code="SUP-21", name="Supplier 21")
    cat = factories.create_category(db_conn, name="Cat FSM")
    uom = factories.create_uom(db_conn, code="PCS-21", name="Pieces", allow_decimal=False)
    item = factories.create_item(db_conn, sku="SKU-21", name="Item 21", category_id=cat["id"], uom_id=uom["id"])

    for usr in (purchasing_user, manager_user, staff_user):
        client.put(
            f"/api/v1/users/{usr['id']}/warehouses",
            headers=superadmin_user["auth_headers"],
            json={"warehouse_ids": [wh["id"]]},
        )

    # 1. PO: DRAFT -> CLOSE tidak diizinkan (hanya dari ISSUED / PARTIALLY_RECEIVED)
    po = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh["id"],
            "order_date": "2026-10-23",
            "lines": [{"item_id": item["id"], "qty_ordered": "10"}],
        },
    ).json()

    bad_close = client.post(
        f"/api/v1/purchase-orders/{po['id']}/close",
        headers=manager_user["auth_headers"],
        json={"closed_reason": "Tutup paksa draft"},
    )
    assert bad_close.status_code == 409
    assert bad_close.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    # Batalkan PO -> CANCELLED
    client.post(
        f"/api/v1/purchase-orders/{po['id']}/cancel",
        headers=purchasing_user["auth_headers"],
        json={"cancelled_reason": "Batal"},
    )

    # PO yang CANCELLED tidak bisa di-issue kembali -> 409 INVALID_STATE_TRANSITION
    bad_issue = client.post(
        f"/api/v1/purchase-orders/{po['id']}/issue",
        headers=purchasing_user["auth_headers"],
    )
    assert bad_issue.status_code == 409
    assert bad_issue.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_ac22_audit_log_completeness_secret_sanitization_and_filter(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    staff_user: dict[str, Any],
    auditor_user: dict[str, Any],
) -> None:
    """AC-22: Kelengkapan Audit Log, Sanitasi Rahasia, dan Otorisasi Pembacaan.
    - Password / hash password / token tidak boleh tersimpan di kolom old_values / new_values audit_logs.
    - Hanya Super Admin dan Auditor yang berhak membaca endpoint /api/v1/audit-logs.
    - Filter audit logs (entity_type, action, user_id, date range).
    """
    role_row = db_conn.execute("SELECT id FROM roles WHERE name = 'Warehouse Staff'").fetchone()
    assert role_row is not None
    staff_role_id = role_row["id"]

    # 1. Buat user baru -> pastikan password tidak bocor di audit log
    new_user_res = client.post(
        "/api/v1/users",
        headers=superadmin_user["auth_headers"],
        json={
            "username": "audit_victim",
            "full_name": "Korban Audit",
            "email": "victim@jejakstok.local",
            "password": "PasswordSangatRahasia123!",
            "role_id": staff_role_id,
        },
    )
    assert new_user_res.status_code == 201
    victim_id = new_user_res.json()["id"]

    # Cek audit log pembuatan user
    log_create = db_conn.execute(
        "SELECT * FROM audit_logs WHERE entity_type = 'users' AND entity_id = %s AND action = 'USER_CREATED'",
        (str(victim_id),),
    ).fetchone()
    assert log_create is not None
    # Password plaintext maupun hash password tidak boleh ada di new_values
    new_vals_str = str(log_create["new_values"])
    assert "PasswordSangatRahasia123!" not in new_vals_str
    assert "password_hash" not in log_create["new_values"]
    assert "password" not in log_create["new_values"]

    # 2. Hak akses pembacaan audit logs: Warehouse Staff ditolak 403 PERMISSION_DENIED
    denied_res = client.get("/api/v1/audit-logs", headers=staff_user["auth_headers"])
    assert denied_res.status_code == 403
    assert denied_res.json()["error"]["code"] == "PERMISSION_DENIED"

    # Auditor berhak membaca audit logs (200 OK)
    auditor_res = client.get(
        f"/api/v1/audit-logs?entity_type=users&action=USER_CREATED",
        headers=auditor_user["auth_headers"],
    )
    assert auditor_res.status_code == 200
    assert auditor_res.json()["total"] >= 1
