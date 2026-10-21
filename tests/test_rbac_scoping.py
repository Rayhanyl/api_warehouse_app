"""Pengujian RBAC, Verifikasi Peran per Request, Audit Log (AC-05), dan Warehouse Scoping (AC-12)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection

from app.core.exceptions import WarehouseNotAssigned
from app.services import access_service
from tests import factories


def test_ac05_rbac_enforcement_and_audit_log_recording(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    staff_user: dict[str, Any],
    auditor_user: dict[str, Any],
    manager_user: dict[str, Any],
) -> None:
    """AC-05 (Kepatuhan RBAC & Audit Log):
    - Pengguna tanpa permission yang sesuai ditolak dengan HTTP 403 PERMISSION_DENIED.
    - Saat perubahan data yang sah berhasil dilakukan, satu baris baru otomatis tercatat di audit_logs
      dengan informasi pengguna, waktu, identitas entitas, serta data sebelum dan sesudah perubahan.
    """
    # 1. Warehouse Staff mencoba mengelola pengguna (butuh user:manage) -> 403 PERMISSION_DENIED
    forbidden_res = client.get("/api/v1/users", headers=staff_user["auth_headers"])
    assert forbidden_res.status_code == 403
    assert forbidden_res.json()["error"]["code"] == "PERMISSION_DENIED"

    # 2. Warehouse Staff mencoba membaca audit log (butuh audit:read) -> 403 PERMISSION_DENIED
    forbidden_audit = client.get("/api/v1/audit-logs", headers=staff_user["auth_headers"])
    assert forbidden_audit.status_code == 403
    assert forbidden_audit.json()["error"]["code"] == "PERMISSION_DENIED"

    # 3. Super Admin mengubah data pengguna (nama lengkap & role) -> berhasil 200 & tercatat old_values/new_values di audit_logs
    patch_res = client.patch(
        f"/api/v1/users/{staff_user['id']}",
        headers=superadmin_user["auth_headers"],
        json={
            "full_name": "Operator Gudang Senior",
            "role_id": manager_user["role_id"],
        },
    )
    assert patch_res.status_code == 200
    updated_data = patch_res.json()
    assert updated_data["full_name"] == "Operator Gudang Senior"
    assert updated_data["role_name"] == "Warehouse Manager"

    # Verifikasi baris audit_logs memiliki user_id, entity_type, entity_id, old_values, dan new_values
    audit_row = db_conn.execute(
        """
        SELECT user_id, action, entity_type, entity_id, old_values, new_values, created_at
        FROM audit_logs
        WHERE action = 'USER_UPDATED' AND entity_type = 'users' AND entity_id = %s
        """,
        (str(staff_user["id"]),),
    ).fetchone()
    assert audit_row is not None
    assert int(audit_row["user_id"]) == int(superadmin_user["id"])
    assert audit_row["old_values"]["full_name"] == "Warehouse Staff User"
    assert audit_row["old_values"]["role_name"] == "Warehouse Staff"
    assert audit_row["new_values"]["full_name"] == "Operator Gudang Senior"
    assert audit_row["new_values"]["role_name"] == "Warehouse Manager"

    # 4. Invarian 14 & FR-01: Peran & status aktif diverifikasi dari DB pada setiap request tanpa menunggu token kedaluwarsa.
    #    Jika pengguna dinonaktifkan oleh Super Admin, token akses yang masih berumur 15 menit langsung ditolak (401).
    deact_res = client.patch(
        f"/api/v1/users/{staff_user['id']}",
        headers=superadmin_user["auth_headers"],
        json={"is_active": False},
    )
    assert deact_res.status_code == 200
    me_res = client.get("/api/v1/auth/me", headers=staff_user["auth_headers"])
    assert me_res.status_code == 401
    assert me_res.json()["error"]["code"] == "AUTH_TOKEN_INVALID"

    # 5. Auditor dapat membaca Audit Log (memiliki audit:read)
    audit_list_res = client.get("/api/v1/audit-logs", headers=auditor_user["auth_headers"])
    assert audit_list_res.status_code == 200
    assert audit_list_res.json()["total"] >= 2

    # 6. Pencegahan self-lockout: Super Admin tidak boleh menonaktifkan dirinya sendiri
    #    atau menghapus permission user:manage dari role Super Admin
    self_deact = client.patch(
        f"/api/v1/users/{superadmin_user['id']}",
        headers=superadmin_user["auth_headers"],
        json={"is_active": False},
    )
    assert self_deact.status_code == 422
    assert self_deact.json()["error"]["code"] == "VALIDATION_ERROR"

    strip_perm = client.put(
        f"/api/v1/users/roles/{superadmin_user['role_id']}/permissions",
        headers=superadmin_user["auth_headers"],
        json={"permissions": ["master:read"]},
    )
    assert strip_perm.status_code == 422
    assert strip_perm.json()["error"]["code"] == "VALIDATION_ERROR"


def test_ac12_warehouse_scoping_assignment_and_access_enforcement(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-12 (Warehouse Scoping):
    - Given Warehouse Staff / Warehouse Manager yang hanya ditugaskan pada Gudang A,
    - When pengguna tersebut diperiksa aksesnya untuk Gudang A, Then diizinkan.
    - When pengguna tersebut mencoba mengakses/memproses aksi bertanda (g) pada Gudang B
      (termasuk endpoint lokasi penyimpanan `location:manage`),
      Then sistem menolak dengan HTTP 403 dan kode WAREHOUSE_NOT_ASSIGNED.
    - Super Admin tidak dibatasi oleh penugasan gudang.
    """
    wh_a = factories.create_warehouse(db_conn, code="WH-A", name="Gudang A")
    wh_b = factories.create_warehouse(db_conn, code="WH-B", name="Gudang B")

    # Super Admin menugaskan staff_user dan manager_user hanya ke Gudang A
    for uid in (staff_user["id"], manager_user["id"]):
        assign_res = client.put(
            f"/api/v1/users/{uid}/warehouses",
            headers=superadmin_user["auth_headers"],
            json={"warehouse_ids": [wh_a["id"]]},
        )
        assert assign_res.status_code == 200
        assigned_list = assign_res.json()
        assert len(assigned_list) == 1
        assert assigned_list[0]["warehouse_id"] == wh_a["id"]

    # Cek profil /auth/me milik staff_user memuat warehouse_ids = [wh_a.id]
    me_res = client.get("/api/v1/auth/me", headers=staff_user["auth_headers"])
    assert me_res.status_code == 200
    actor_ctx = me_res.json()
    assert actor_ctx["warehouse_ids"] == [wh_a["id"]]

    # Akses ke Gudang A berhasil
    access_service.ensure_warehouse_access(db_conn, actor_ctx, int(wh_a["id"]))

    # Akses ke Gudang B ditolak dengan WarehouseNotAssigned (HTTP 403 WAREHOUSE_NOT_ASSIGNED)
    try:
        access_service.ensure_warehouse_access(db_conn, actor_ctx, int(wh_b["id"]))
        raise AssertionError("Seharusnya melempar WarehouseNotAssigned untuk Gudang B")
    except WarehouseNotAssigned as exc:
        assert exc.http_status == 403
        assert exc.code == "WAREHOUSE_NOT_ASSIGNED"
        assert exc.details["warehouse_id"] == int(wh_b["id"])

    # Uji melalui HTTP endpoint bertanda (g): Warehouse Manager membuat lokasi di Gudang A -> 201
    loc_a_res = client.post(
        f"/api/v1/warehouses/{wh_a['id']}/locations",
        headers=manager_user["auth_headers"],
        json={"code": "BIN-A01", "name": "Bin A01"},
    )
    assert loc_a_res.status_code == 201
    assert loc_a_res.json()["code"] == "BIN-A01"

    # Warehouse Manager mencoba membuat lokasi di Gudang B (tidak ditugaskan) -> 403 WAREHOUSE_NOT_ASSIGNED
    loc_b_forbidden = client.post(
        f"/api/v1/warehouses/{wh_b['id']}/locations",
        headers=manager_user["auth_headers"],
        json={"code": "BIN-B01", "name": "Bin B01"},
    )
    assert loc_b_forbidden.status_code == 403
    assert loc_b_forbidden.json()["error"]["code"] == "WAREHOUSE_NOT_ASSIGNED"

    # Super Admin bebas membuat lokasi di Gudang B meskipun tidak ada di user_warehouses
    loc_b_super = client.post(
        f"/api/v1/warehouses/{wh_b['id']}/locations",
        headers=superadmin_user["auth_headers"],
        json={"code": "BIN-B01", "name": "Bin B01"},
    )
    assert loc_b_super.status_code == 201
    loc_b_id = loc_b_super.json()["id"]

    # Warehouse Manager mencoba mengubah lokasi di Gudang B -> 403 WAREHOUSE_NOT_ASSIGNED
    patch_b_forbidden = client.patch(
        f"/api/v1/locations/{loc_b_id}",
        headers=manager_user["auth_headers"],
        json={"name": "Bin B01 Diubah"},
    )
    assert patch_b_forbidden.status_code == 403
    assert patch_b_forbidden.json()["error"]["code"] == "WAREHOUSE_NOT_ASSIGNED"


def test_master_data_and_warehouse_crud_deactivation_and_sku_immutability(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
    auditor_user: dict[str, Any],
) -> None:
    """FR-02, PRD 6.3, 6.8:
    - CRUD Master Data (Kategori, UoM, Pemasok, Barang) oleh Purchasing Staff (master:manage).
    - CRUD Gudang oleh Super Admin (warehouse:manage) termasuk audit perubahan allow_negative_stock.
    - CRUD Lokasi oleh Warehouse Manager pada gudang yang ditugaskan (location:manage).
    - Validasi referensi tidak aktif (422 INACTIVE_REFERENCE) dan duplikasi (409 DUPLICATE).
    - Aturan penonaktifan (409 ENTITY_IN_USE) saat masih bersaldo != 0 atau ada dokumen belum final.
    - Imutabilitas SKU barang setelah dipakai pada transaksi (409 ENTITY_IN_USE).
    """
    # 1. Warehouse Staff tidak memiliki master:manage -> 403 saat membuat kategori
    staff_cat = client.post(
        "/api/v1/categories",
        headers=staff_user["auth_headers"],
        json={"name": "Bahan Baku"},
    )
    assert staff_cat.status_code == 403
    assert staff_cat.json()["error"]["code"] == "PERMISSION_DENIED"

    # 2. Purchasing Staff membuat Kategori, UoM, Pemasok, dan Barang
    cat_res = client.post(
        "/api/v1/categories",
        headers=purchasing_user["auth_headers"],
        json={"name": "Komponen Elektronik", "description": "IC, Resistor, Kapasitor"},
    )
    assert cat_res.status_code == 201
    cat_id = cat_res.json()["id"]

    # Duplikasi nama kategori -> 409 DUPLICATE
    dup_cat = client.post(
        "/api/v1/categories",
        headers=purchasing_user["auth_headers"],
        json={"name": "komponen elektronik"},
    )
    assert dup_cat.status_code == 409
    assert dup_cat.json()["error"]["code"] == "DUPLICATE"

    uom_res = client.post(
        "/api/v1/uoms",
        headers=purchasing_user["auth_headers"],
        json={"code": "PCS", "name": "Pieces", "allow_decimal": False},
    )
    assert uom_res.status_code == 201
    uom_id = uom_res.json()["id"]

    sup_res = client.post(
        "/api/v1/suppliers",
        headers=purchasing_user["auth_headers"],
        json={
            "code": "SUP-ELK-01",
            "name": "PT Nusantara Elektronik",
            "contact_person": "Hendra",
            "phone": "021-5551234",
            "email": "sales@nusantara.co.id",
            "address": "Kawasan Industri Jababeka",
        },
    )
    assert sup_res.status_code == 201
    sup_id = sup_res.json()["id"]

    item_res = client.post(
        "/api/v1/items",
        headers=purchasing_user["auth_headers"],
        json={
            "sku": "ELK-MCU-001",
            "name": "Microcontroller ESP32",
            "description": "Dual-core Wi-Fi & BLE MCU",
            "category_id": cat_id,
            "uom_id": uom_id,
        },
    )
    assert item_res.status_code == 201
    item_data = item_res.json()
    item_id = item_data["id"]
    assert item_data["category_name"] == "Komponen Elektronik"
    assert item_data["uom_code"] == "PCS"
    assert item_data["allow_decimal"] is False

    # 3. Kategori dan UoM yang dipakai oleh barang aktif tidak boleh dinonaktifkan -> 409 ENTITY_IN_USE
    deact_cat = client.patch(
        f"/api/v1/categories/{cat_id}",
        headers=purchasing_user["auth_headers"],
        json={"is_active": False},
    )
    assert deact_cat.status_code == 409
    assert deact_cat.json()["error"]["code"] == "ENTITY_IN_USE"

    deact_uom = client.patch(
        f"/api/v1/uoms/{uom_id}",
        headers=purchasing_user["auth_headers"],
        json={"is_active": False},
    )
    assert deact_uom.status_code == 409
    assert deact_uom.json()["error"]["code"] == "ENTITY_IN_USE"

    # 4. Super Admin membuat Gudang & mengubah allow_negative_stock (tercatat di audit_logs)
    wh_res = client.post(
        "/api/v1/warehouses",
        headers=superadmin_user["auth_headers"],
        json={
            "code": "WH-JKT-01",
            "name": "Gudang Utama Jakarta",
            "address": "Jl. Raya Cakung Cilincing",
            "allow_negative_stock": False,
        },
    )
    assert wh_res.status_code == 201
    wh_id = wh_res.json()["id"]

    # Purchasing Staff tidak boleh mengelola gudang (butuh warehouse:manage) -> 403
    wh_forbidden = client.patch(
        f"/api/v1/warehouses/{wh_id}",
        headers=purchasing_user["auth_headers"],
        json={"allow_negative_stock": True},
    )
    assert wh_forbidden.status_code == 403

    wh_patch = client.patch(
        f"/api/v1/warehouses/{wh_id}",
        headers=superadmin_user["auth_headers"],
        json={"allow_negative_stock": True},
    )
    assert wh_patch.status_code == 200
    assert wh_patch.json()["allow_negative_stock"] is True

    # Pastikan perubahan allow_negative_stock tercatat di audit_logs
    wh_audit = db_conn.execute(
        """
        SELECT old_values, new_values
        FROM audit_logs
        WHERE action = 'WAREHOUSE_UPDATED' AND entity_type = 'warehouses' AND entity_id = %s
        """,
        (str(wh_id),),
    ).fetchone()
    assert wh_audit is not None
    assert wh_audit["old_values"]["allow_negative_stock"] is False
    assert wh_audit["new_values"]["allow_negative_stock"] is True

    # Buat lokasi penyimpanan pada gudang
    loc_res = client.post(
        "/api/v1/locations",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_id": wh_id, "code": "A-01-01", "name": "Rak A Baris 1"},
    )
    assert loc_res.status_code == 201
    loc_id = loc_res.json()["id"]

    # 5. Sebelum barang dipakai pada transaksi, SKU masih boleh diubah
    sku_change_ok = client.patch(
        f"/api/v1/items/{item_id}",
        headers=purchasing_user["auth_headers"],
        json={"sku": "ELK-MCU-001-REV"},
    )
    assert sku_change_ok.status_code == 200
    assert sku_change_ok.json()["sku"] == "ELK-MCU-001-REV"

    # 6. Simulasikan PO DRAFT aktif & saldo stok > 0 untuk menguji aturan PRD 6.8 (ENTITY_IN_USE & imutabilitas SKU)
    po_row = db_conn.execute(
        """
        INSERT INTO purchase_orders (po_number, supplier_id, warehouse_id, status, order_date, created_by)
        VALUES ('PO-202610-0001', %s, %s, 'DRAFT', CURRENT_DATE, %s)
        RETURNING id
        """,
        (sup_id, wh_id, purchasing_user["id"]),
    ).fetchone()
    assert po_row is not None
    db_conn.execute(
        """
        INSERT INTO po_lines (po_id, item_id, qty_ordered, qty_received, created_by)
        VALUES (%s, %s, 10.0000, 0.0000, %s)
        """,
        (po_row["id"], item_id, purchasing_user["id"]),
    )
    db_conn.execute(
        """
        INSERT INTO inventory_balances (warehouse_id, location_id, item_id, qty_on_hand, created_by)
        VALUES (%s, %s, %s, 5.0000, %s)
        """,
        (wh_id, loc_id, item_id, superadmin_user["id"]),
    )

    # Setelah dipakai pada transaksi, mengubah SKU ditolak dengan 409 ENTITY_IN_USE
    sku_change_blocked = client.patch(
        f"/api/v1/items/{item_id}",
        headers=purchasing_user["auth_headers"],
        json={"sku": "ELK-MCU-999"},
    )
    assert sku_change_blocked.status_code == 409
    assert sku_change_blocked.json()["error"]["code"] == "ENTITY_IN_USE"

    # Menonaktifkan barang, pemasok, gudang, dan lokasi yang sedang aktif dipakai/bersaldo -> 409 ENTITY_IN_USE
    assert (
        client.patch(
            f"/api/v1/items/{item_id}",
            headers=purchasing_user["auth_headers"],
            json={"is_active": False},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/suppliers/{sup_id}",
            headers=purchasing_user["auth_headers"],
            json={"is_active": False},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/warehouses/{wh_id}",
            headers=superadmin_user["auth_headers"],
            json={"is_active": False},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/locations/{loc_id}",
            headers=superadmin_user["auth_headers"],
            json={"is_active": False},
        ).status_code
        == 409
    )

    # 7. Auditor dapat membaca seluruh endpoint daftar dan detail master data (master:read)
    for url in (
        f"/api/v1/categories?search=Komponen",
        f"/api/v1/categories/{cat_id}",
        f"/api/v1/uoms?search=PCS",
        f"/api/v1/uoms/{uom_id}",
        f"/api/v1/suppliers?search=Nusantara",
        f"/api/v1/suppliers/{sup_id}",
        f"/api/v1/items?category_id={cat_id}&uom_id={uom_id}&search=ESP32",
        f"/api/v1/items/{item_id}",
        f"/api/v1/warehouses?search=Jakarta",
        f"/api/v1/warehouses/{wh_id}",
        f"/api/v1/warehouses/{wh_id}/locations",
        f"/api/v1/locations?warehouse_id={wh_id}&search=A-01",
        f"/api/v1/locations/{loc_id}",
    ):
        res = client.get(url, headers=auditor_user["auth_headers"])
        assert res.status_code == 200, f"Gagal GET {url}: {res.text}"

    # 8. Uji update dan penonaktifan berhasil pada entitas yang tidak dipakai di transaksi,
    #    serta penolakan INACTIVE_REFERENCE (422) saat membuat barang/lokasi dengan referensi nonaktif
    cat2 = client.post(
        "/api/v1/categories",
        headers=purchasing_user["auth_headers"],
        json={"name": "Kategori Cadangan"},
    ).json()
    cat2_upd = client.patch(
        f"/api/v1/categories/{cat2['id']}",
        headers=purchasing_user["auth_headers"],
        json={"name": "Kategori Cadangan Baru", "is_active": False},
    )
    assert cat2_upd.status_code == 200
    assert cat2_upd.json()["is_active"] is False

    # Membuat barang dengan kategori nonaktif -> 422 INACTIVE_REFERENCE
    inactive_cat_item = client.post(
        "/api/v1/items",
        headers=purchasing_user["auth_headers"],
        json={
            "sku": "SKU-INACTIVE-CAT",
            "name": "Barang Gagal",
            "category_id": cat2["id"],
            "uom_id": uom_id,
        },
    )
    assert inactive_cat_item.status_code == 422
    assert inactive_cat_item.json()["error"]["code"] == "INACTIVE_REFERENCE"

    uom2 = client.post(
        "/api/v1/uoms",
        headers=purchasing_user["auth_headers"],
        json={"code": "KG", "name": "Kilogram", "allow_decimal": True},
    ).json()
    uom2_upd = client.patch(
        f"/api/v1/uoms/{uom2['id']}",
        headers=purchasing_user["auth_headers"],
        json={"name": "Kilogram Metric", "is_active": False},
    )
    assert uom2_upd.status_code == 200
    assert uom2_upd.json()["is_active"] is False

    sup2 = client.post(
        "/api/v1/suppliers",
        headers=purchasing_user["auth_headers"],
        json={"code": "SUP-CAD-02", "name": "CV Mitra Cadangan"},
    ).json()
    sup2_upd = client.patch(
        f"/api/v1/suppliers/{sup2['id']}",
        headers=purchasing_user["auth_headers"],
        json={"name": "CV Mitra Cadangan Utama", "is_active": False},
    )
    assert sup2_upd.status_code == 200
    assert sup2_upd.json()["is_active"] is False

    wh2 = client.post(
        "/api/v1/warehouses",
        headers=superadmin_user["auth_headers"],
        json={"code": "WH-SBY-02", "name": "Gudang Surabaya"},
    ).json()
    loc2 = client.post(
        "/api/v1/locations",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_id": wh2["id"], "code": "SBY-01", "name": "Rak SBY 1"},
    ).json()
    loc2_upd = client.patch(
        f"/api/v1/locations/{loc2['id']}",
        headers=superadmin_user["auth_headers"],
        json={"name": "Rak SBY 1 Baru", "is_active": False},
    )
    assert loc2_upd.status_code == 200
    assert loc2_upd.json()["is_active"] is False

    wh2_upd = client.patch(
        f"/api/v1/warehouses/{wh2['id']}",
        headers=superadmin_user["auth_headers"],
        json={"is_active": False},
    )
    assert wh2_upd.status_code == 200
    assert wh2_upd.json()["is_active"] is False

    # Membuat lokasi pada gudang nonaktif -> 422 INACTIVE_REFERENCE
    inactive_wh_loc = client.post(
        "/api/v1/locations",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_id": wh2["id"], "code": "SBY-02", "name": "Rak SBY 2"},
    )
    assert inactive_wh_loc.status_code == 422
    assert inactive_wh_loc.json()["error"]["code"] == "INACTIVE_REFERENCE"



