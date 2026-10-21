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


def test_ac12_warehouse_scoping_assignment_and_access_enforcement(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """AC-12 (Warehouse Scoping):
    - Given Warehouse Staff yang hanya ditugaskan pada Gudang A,
    - When pengguna tersebut diperiksa aksesnya untuk Gudang A, Then diizinkan.
    - When pengguna tersebut mencoba mengakses/memproses aksi bertanda (g) pada Gudang B,
      Then sistem menolak dengan HTTP 403 dan kode WAREHOUSE_NOT_ASSIGNED.
    - Super Admin tidak dibatasi oleh penugasan gudang.
    """
    wh_a = factories.create_warehouse(db_conn, code="WH-A", name="Gudang A")
    wh_b = factories.create_warehouse(db_conn, code="WH-B", name="Gudang B")

    # Super Admin menugaskan staff_user hanya ke Gudang A lewat endpoint PUT /api/v1/users/{id}/warehouses
    assign_res = client.put(
        f"/api/v1/users/{staff_user['id']}/warehouses",
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

    # Super Admin bebas mengakses Gudang B meskipun tidak ada di user_warehouses
    superadmin_me = client.get(
        "/api/v1/auth/me", headers=superadmin_user["auth_headers"]
    ).json()
    access_service.ensure_warehouse_access(db_conn, superadmin_me, int(wh_b["id"]))

