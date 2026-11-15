"""Pengujian komprehensif Tahap 34 (Multi-Level Approval PO & Stock Opname + Ekspansi Role + Settings)
dan Tahap 38 (Segregation of Duties: gr:create/gr:post & maker-checker pada GR, Transfer, Opname, PO).
"""

from decimal import Decimal
import json
from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection

from tests import factories


def _assign_warehouse(
    client: TestClient,
    superadmin_headers: dict[str, str],
    warehouse_id: int,
    *users: dict[str, Any],
) -> None:
    for usr in users:
        res = client.put(
            f"/api/v1/users/{usr['id']}/warehouses",
            headers=superadmin_headers,
            json={"warehouse_ids": [warehouse_id]},
        )
        assert res.status_code == 200


def test_tahap34_roles_permissions_and_approval_threshold_settings(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    supervisor_user: dict[str, Any],
    manager_user: dict[str, Any],
    procurement_manager_user: dict[str, Any],
    purchasing_user: dict[str, Any],
) -> None:
    roles_res = client.get("/api/v1/users/roles", headers=superadmin_user["auth_headers"])
    assert roles_res.status_code == 200
    roles_by_name = {r["name"]: set(r["permissions"]) for r in roles_res.json()}

    assert "Warehouse Supervisor" in roles_by_name
    assert "Procurement Manager" in roles_by_name
    assert "gr:post" in roles_by_name["Warehouse Supervisor"]
    assert "opname:approve_l1" in roles_by_name["Warehouse Supervisor"]
    assert "opname:approve_l2" not in roles_by_name["Warehouse Supervisor"]
    assert "po:approve_l1" in roles_by_name["Procurement Manager"]
    assert "po:approve_l2" in roles_by_name["Procurement Manager"]
    assert "settings:manage" in roles_by_name["Super Admin"]

    perms_res = client.get("/api/v1/users/permissions", headers=superadmin_user["auth_headers"])
    assert perms_res.status_code == 200
    perm_codes = {p["code"] for p in perms_res.json()}
    assert {
        "gr:create",
        "gr:post",
        "po:approve_l1",
        "po:approve_l2",
        "opname:approve_l1",
        "opname:approve_l2",
        "settings:manage",
    }.issubset(perm_codes)
    assert "gr:manage" not in perm_codes
    assert "opname:approve" not in perm_codes

    # Pengaturan threshold default = 10000000.00
    get_res = client.get("/api/v1/settings/approval", headers=purchasing_user["auth_headers"])
    assert get_res.status_code == 200
    assert get_res.json()["po_l2_approval_threshold"] == "10000000.00"

    # Non-Super Admin ditolak mengubah settings -> 403
    for non_admin in (manager_user, supervisor_user, procurement_manager_user):
        denied = client.put(
            "/api/v1/settings/approval",
            headers=non_admin["auth_headers"],
            json={"po_l2_approval_threshold": "5000000"},
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    # Nilai negatif ditolak 422
    neg = client.put(
        "/api/v1/settings/approval",
        headers=superadmin_user["auth_headers"],
        json={"po_l2_approval_threshold": "-100"},
    )
    assert neg.status_code == 422

    # Super Admin berhasil memperbarui ambang batas -> tercatat di audit_logs
    upd = client.put(
        "/api/v1/settings/approval",
        headers=superadmin_user["auth_headers"],
        json={"po_l2_approval_threshold": "7500000"},
    )
    assert upd.status_code == 200
    assert upd.json()["po_l2_approval_threshold"] == "7500000.00"

    audit_row = db_conn.execute(
        "SELECT * FROM audit_logs WHERE action = 'SETTINGS_UPDATED' AND entity_type = 'app_settings' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert audit_row is not None


def test_tahap38_sod_gr_split_and_transfer_with_superadmin_override_audit(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    supervisor_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    wh1 = factories.create_warehouse(db_conn, code="WH-SOD1", name="Gudang SoD 1")
    wh2 = factories.create_warehouse(db_conn, code="WH-SOD2", name="Gudang SoD 2")
    loc1 = factories.create_location(db_conn, warehouse_id=wh1["id"], code="R-1", name="Rak 1")
    loc2 = factories.create_location(db_conn, warehouse_id=wh2["id"], code="R-2", name="Rak 2")
    sup = factories.create_supplier(db_conn, code="SUP-SOD", name="Supplier SoD")
    cat = factories.create_category(db_conn, name="Kat SoD")
    uom = factories.create_uom(db_conn, code="PCS-SOD", name="Pieces", allow_decimal=False)
    item = factories.create_item(db_conn, sku="SKU-SOD", name="Item SoD", category_id=cat["id"], uom_id=uom["id"])

    for usr in (purchasing_user, supervisor_user, manager_user, staff_user):
        client.put(
            f"/api/v1/users/{usr['id']}/warehouses",
            headers=superadmin_user["auth_headers"],
            json={"warehouse_ids": [wh1["id"], wh2["id"]]},
        )

    po = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh1["id"],
            "order_date": "2026-11-15",
            "lines": [{"item_id": item["id"], "qty_ordered": "30"}],
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po['id']}/issue",
            headers=manager_user["auth_headers"],
        ).status_code
        == 200
    )

    # 1. Warehouse Staff membuat GR (gr:create) tetapi ditolak posting (tanpa gr:post) -> 403
    gr_staff = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-11-15",
            "lines": [{"po_line_id": po["lines"][0]["id"], "location_id": loc1["id"], "qty_received": "10"}],
        },
    ).json()
    staff_post_denied = client.post(
        f"/api/v1/goods-receipts/{gr_staff['id']}/post",
        headers=staff_user["auth_headers"],
    )
    assert staff_post_denied.status_code == 403

    # Supervisor mem-posting GR milik Staff -> 200 POSTED
    sup_post_ok = client.post(
        f"/api/v1/goods-receipts/{gr_staff['id']}/post",
        headers=supervisor_user["auth_headers"],
    )
    assert sup_post_ok.status_code == 200
    assert sup_post_ok.json()["status"] == "POSTED"

    # 2. Supervisor membuat GR sendiri lalu mencoba mem-posting GR miliknya sendiri -> 403 SOD_VIOLATION
    gr_sup = client.post(
        "/api/v1/goods-receipts",
        headers=supervisor_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-11-15",
            "lines": [{"po_line_id": po["lines"][0]["id"], "location_id": loc1["id"], "qty_received": "10"}],
        },
    ).json()
    sup_self_post = client.post(
        f"/api/v1/goods-receipts/{gr_sup['id']}/post",
        headers=supervisor_user["auth_headers"],
    )
    assert sup_self_post.status_code == 403
    assert sup_self_post.json()["error"]["details"]["code"] == "SOD_VIOLATION"

    # 3. Super Admin membuat & self-posting GR -> diizinkan (exception), details audit mencatat sod_override=true
    gr_sa = client.post(
        "/api/v1/goods-receipts",
        headers=superadmin_user["auth_headers"],
        json={
            "po_id": po["id"],
            "received_date": "2026-11-15",
            "lines": [{"po_line_id": po["lines"][0]["id"], "location_id": loc1["id"], "qty_received": "10"}],
        },
    ).json()
    sa_self_post = client.post(
        f"/api/v1/goods-receipts/{gr_sa['id']}/post",
        headers=superadmin_user["auth_headers"],
    )
    assert sa_self_post.status_code == 200

    gr_override_audit = db_conn.execute(
        "SELECT details FROM audit_logs WHERE entity_type = 'goods_receipts' AND entity_id = %s AND action = 'GR_POSTED' ORDER BY id DESC LIMIT 1",
        (str(gr_sa["id"]),),
    ).fetchone()
    assert gr_override_audit is not None
    details = (
        json.loads(gr_override_audit["details"])
        if isinstance(gr_override_audit["details"], str)
        else gr_override_audit["details"]
    )
    assert details.get("sod_override") is True

    # 4. Transfer SoD: Supervisor membuat transfer -> tidak boleh approve sendiri -> 403 SOD_VIOLATION
    trf_sup = client.post(
        "/api/v1/stock-transfers",
        headers=supervisor_user["auth_headers"],
        json={
            "source_warehouse_id": wh1["id"],
            "source_location_id": loc1["id"],
            "destination_warehouse_id": wh2["id"],
            "destination_location_id": loc2["id"],
            "transfer_date": "2026-11-15",
            "lines": [{"item_id": item["id"], "qty": "5"}],
        },
    ).json()
    sup_self_approve = client.post(
        f"/api/v1/stock-transfers/{trf_sup['id']}/approve",
        headers=supervisor_user["auth_headers"],
    )
    assert sup_self_approve.status_code == 403
    assert sup_self_approve.json()["error"]["details"]["code"] == "SOD_VIOLATION"

    # Manager menyetujui transfer milik Supervisor -> 200 APPROVED
    mgr_approve = client.post(
        f"/api/v1/stock-transfers/{trf_sup['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    assert mgr_approve.status_code == 200
    assert mgr_approve.json()["status"] == "APPROVED"

    # Super Admin membuat & self-approve transfer -> 200 APPROVED + sod_override=true
    trf_sa = client.post(
        "/api/v1/stock-transfers",
        headers=superadmin_user["auth_headers"],
        json={
            "source_warehouse_id": wh1["id"],
            "source_location_id": loc1["id"],
            "destination_warehouse_id": wh2["id"],
            "destination_location_id": loc2["id"],
            "transfer_date": "2026-11-15",
            "lines": [{"item_id": item["id"], "qty": "2"}],
        },
    ).json()
    sa_self_approve = client.post(
        f"/api/v1/stock-transfers/{trf_sa['id']}/approve",
        headers=superadmin_user["auth_headers"],
    )
    assert sa_self_approve.status_code == 200
    trf_override_audit = db_conn.execute(
        "SELECT details FROM audit_logs WHERE entity_type = 'stock_transfers' AND entity_id = %s AND action = 'TRANSFER_APPROVED' ORDER BY id DESC LIMIT 1",
        (str(trf_sa["id"]),),
    ).fetchone()
    assert trf_override_audit is not None
    trf_details = (
        json.loads(trf_override_audit["details"])
        if isinstance(trf_override_audit["details"], str)
        else trf_override_audit["details"]
    )
    assert trf_details.get("sod_override") is True


def test_tahap34_po_multi_level_approval_pricing_reject_and_resubmit(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    manager_user: dict[str, Any],
    procurement_manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    wh = factories.create_warehouse(db_conn, code="WH-PO-ML", name="Gudang PO Multi-Level")
    loc = factories.create_location(db_conn, warehouse_id=wh["id"], code="R-PO", name="Rak PO")
    sup = factories.create_supplier(db_conn, code="SUP-ML", name="Supplier ML")
    cat = factories.create_category(db_conn, name="Kat PO ML")
    uom = factories.create_uom(db_conn, code="PCS-ML", name="Pieces", allow_decimal=False)
    item = factories.create_item(db_conn, sku="SKU-POML", name="Server Rack", category_id=cat["id"], uom_id=uom["id"])

    _assign_warehouse(
        client,
        superadmin_user["auth_headers"],
        wh["id"],
        purchasing_user,
        manager_user,
        procurement_manager_user,
        staff_user,
    )

    # A. PO tanpa unit_price (total_amount = 0.00 <= 10jt) -> cukup L1 untuk menjadi ISSUED
    po_low = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh["id"],
            "order_date": "2026-11-15",
            "lines": [{"item_id": item["id"], "qty_ordered": "5"}],
        },
    ).json()
    assert po_low["total_amount"] == "0.00"
    assert po_low["lines"][0]["unit_price"] == "0.00"

    sub_low = client.post(
        f"/api/v1/purchase-orders/{po_low['id']}/submit",
        headers=purchasing_user["auth_headers"],
    )
    assert sub_low.status_code == 200
    assert sub_low.json()["status"] == "WAITING_L1_APPROVAL"

    # Purchasing Staff tidak boleh self-approve -> 403
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po_low['id']}/approve",
            headers=purchasing_user["auth_headers"],
        ).status_code
        == 403
    )

    # Warehouse Manager approve L1 -> langsung ISSUED karena total 0 <= threshold 10jt
    app_low = client.post(
        f"/api/v1/purchase-orders/{po_low['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    assert app_low.status_code == 200
    assert app_low.json()["status"] == "ISSUED"
    assert [l["action"] for l in app_low.json()["approval_logs"]] == ["SUBMITTED", "APPROVED"]

    # B. PO dengan total_amount = 10 * 1.500.000 = 15.000.000 (> 10.000.000) -> Wajib L1 + L2
    po_high = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh["id"],
            "order_date": "2026-11-15",
            "lines": [{"item_id": item["id"], "qty_ordered": "10", "unit_price": "1500000"}],
        },
    ).json()
    assert po_high["total_amount"] == "15000000.00"
    assert po_high["lines"][0]["line_subtotal"] == "15000000.00"

    # Direct /issue pada PO di atas threshold ditolak -> wajib lewat submit & approve
    direct_issue = client.post(
        f"/api/v1/purchase-orders/{po_high['id']}/issue",
        headers=manager_user["auth_headers"],
    )
    assert direct_issue.status_code == 409

    # Submit -> WAITING_L1_APPROVAL
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po_high['id']}/submit",
            headers=purchasing_user["auth_headers"],
        ).status_code
        == 200
    )

    # L1 Approve oleh Warehouse Manager -> WAITING_L2_APPROVAL (belum boleh GR)
    l1_res = client.post(
        f"/api/v1/purchase-orders/{po_high['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    assert l1_res.status_code == 200
    assert l1_res.json()["status"] == "WAITING_L2_APPROVAL"

    gr_blocked = client.post(
        "/api/v1/goods-receipts",
        headers=staff_user["auth_headers"],
        json={
            "po_id": po_high["id"],
            "received_date": "2026-11-15",
            "lines": [{"po_line_id": po_high["lines"][0]["id"], "location_id": loc["id"], "qty_received": "1"}],
        },
    )
    assert gr_blocked.status_code == 409

    # Warehouse Manager tidak memiliki po:approve_l2 -> 403
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po_high['id']}/approve",
            headers=manager_user["auth_headers"],
        ).status_code
        == 403
    )

    # Reject L2 wajib alasan; lalu reject sukses kembali ke DRAFT
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po_high['id']}/reject",
            headers=procurement_manager_user["auth_headers"],
            json={"rejection_reason": "   "},
        ).status_code
        == 422
    )
    rej_res = client.post(
        f"/api/v1/purchase-orders/{po_high['id']}/reject",
        headers=procurement_manager_user["auth_headers"],
        json={"rejection_reason": "Negosiasi ulang harga satuan"},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "DRAFT"
    assert rej_res.json()["rejection_reason"] == "Negosiasi ulang harga satuan"

    # Purchasing Staff edit draft -> resubmit -> L1 (Manager) -> L2 (Procurement Manager) -> ISSUED
    patch_res = client.patch(
        f"/api/v1/purchase-orders/{po_high['id']}",
        headers=purchasing_user["auth_headers"],
        json={"lines": [{"item_id": item["id"], "qty_ordered": "10", "unit_price": "1200000"}]},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["total_amount"] == "12000000.00"

    assert (
        client.post(
            f"/api/v1/purchase-orders/{po_high['id']}/submit",
            headers=purchasing_user["auth_headers"],
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po_high['id']}/approve",
            headers=manager_user["auth_headers"],
        ).json()["status"]
        == "WAITING_L2_APPROVAL"
    )
    l2_ok = client.post(
        f"/api/v1/purchase-orders/{po_high['id']}/approve",
        headers=procurement_manager_user["auth_headers"],
    )
    assert l2_ok.status_code == 200
    assert l2_ok.json()["status"] == "ISSUED"
    assert l2_ok.json()["l1_approved_by"] == manager_user["id"]
    assert l2_ok.json()["l2_approved_by"] == procurement_manager_user["id"]
    assert len(l2_ok.json()["approval_logs"]) == 6

    # C. SoD L2: bila Procurement Manager menyetujui L1 sendiri, ia tidak boleh menyetujui L2 sendiri -> 403 SOD_VIOLATION
    client.put(
        "/api/v1/settings/approval",
        headers=superadmin_user["auth_headers"],
        json={"po_l2_approval_threshold": "100000"},
    )
    po_sod_l2 = client.post(
        "/api/v1/purchase-orders",
        headers=purchasing_user["auth_headers"],
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh["id"],
            "order_date": "2026-11-15",
            "lines": [{"item_id": item["id"], "qty_ordered": "2", "unit_price": "100000"}],
        },
    ).json()
    client.post(f"/api/v1/purchase-orders/{po_sod_l2['id']}/submit", headers=purchasing_user["auth_headers"])
    assert (
        client.post(
            f"/api/v1/purchase-orders/{po_sod_l2['id']}/approve",
            headers=procurement_manager_user["auth_headers"],
        ).json()["status"]
        == "WAITING_L2_APPROVAL"
    )
    self_l2 = client.post(
        f"/api/v1/purchase-orders/{po_sod_l2['id']}/approve",
        headers=procurement_manager_user["auth_headers"],
    )
    assert self_l2.status_code == 403
    assert self_l2.json()["error"]["details"]["code"] == "SOD_VIOLATION"


def test_tahap34_38_opname_two_level_approval_sod_and_superadmin_override(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    supervisor_user: dict[str, Any],
    manager_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    wh = factories.create_warehouse(db_conn, code="WH-OP-ML", name="Gudang Opname ML")
    loc = factories.create_location(db_conn, warehouse_id=wh["id"], code="R-OP", name="Rak Opname")
    cat = factories.create_category(db_conn, name="Kat Opname ML")
    uom = factories.create_uom(db_conn, code="PCS-OPML", name="Pieces", allow_decimal=False)
    item = factories.create_item(db_conn, sku="SKU-OPML", name="Barang Opname ML", category_id=cat["id"], uom_id=uom["id"])

    _assign_warehouse(
        client,
        superadmin_user["auth_headers"],
        wh["id"],
        supervisor_user,
        manager_user,
        staff_user,
    )

    opn = client.post(
        "/api/v1/stock-opnames",
        headers=manager_user["auth_headers"],
        json={"warehouse_id": wh["id"], "location_id": loc["id"]},
    ).json()
    client.post(f"/api/v1/stock-opnames/{opn['id']}/start", headers=manager_user["auth_headers"])

    # Supervisor menghitung fisik & mengajukan submit
    client.post(
        f"/api/v1/stock-opnames/{opn['id']}/count",
        headers=supervisor_user["auth_headers"],
        json={"lines": [{"location_id": loc["id"], "item_id": item["id"], "qty_physical": "7"}]},
    )
    sub_res = client.post(
        f"/api/v1/stock-opnames/{opn['id']}/submit",
        headers=supervisor_user["auth_headers"],
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "WAITING_L1_APPROVAL"

    # Supervisor yang menghitung/mengajukan ditolak menyetujui L1 sendiri -> 403 SOD_VIOLATION
    self_opn_l1 = client.post(
        f"/api/v1/stock-opnames/{opn['id']}/approve",
        headers=supervisor_user["auth_headers"],
    )
    assert self_opn_l1.status_code == 403
    assert self_opn_l1.json()["error"]["details"]["code"] == "SOD_VIOLATION"

    # Super Admin melakukan SoD override approve L1 -> WAITING_L2_APPROVAL (tercatat sod_override=true)
    sa_l1 = client.post(
        f"/api/v1/stock-opnames/{opn['id']}/approve",
        headers=superadmin_user["auth_headers"],
    )
    # Catatan: Super Admin bukan counter, jadi tidak memicu SoD pada L1 ini; Manager lanjut L2
    assert sa_l1.status_code == 200
    assert sa_l1.json()["status"] == "WAITING_L2_APPROVAL"

    # Manager approve L2 -> COMPLETED
    mgr_l2 = client.post(
        f"/api/v1/stock-opnames/{opn['id']}/approve",
        headers=manager_user["auth_headers"],
    )
    assert mgr_l2.status_code == 200
    completed = mgr_l2.json()
    assert completed["status"] == "COMPLETED"
    assert completed["l1_approved_by"] == superadmin_user["id"]
    assert completed["l2_approved_by"] == manager_user["id"]
    assert [log["action"] for log in completed["approval_logs"]] == ["SUBMITTED", "APPROVED", "APPROVED"]

    # Super Admin melakukan full self-count, self-submit, self-L1, dan self-L2 pada opname baru -> sod_override=true tercatat
    opn2 = client.post(
        "/api/v1/stock-opnames",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_id": wh["id"], "location_id": loc["id"]},
    ).json()
    client.post(f"/api/v1/stock-opnames/{opn2['id']}/start", headers=superadmin_user["auth_headers"])
    client.post(
        f"/api/v1/stock-opnames/{opn2['id']}/count",
        headers=superadmin_user["auth_headers"],
        json={"lines": [{"location_id": loc["id"], "item_id": item["id"], "qty_physical": "9"}]},
    )
    client.post(f"/api/v1/stock-opnames/{opn2['id']}/submit", headers=superadmin_user["auth_headers"])
    assert (
        client.post(
            f"/api/v1/stock-opnames/{opn2['id']}/approve",
            headers=superadmin_user["auth_headers"],
        ).json()["status"]
        == "WAITING_L2_APPROVAL"
    )
    assert (
        client.post(
            f"/api/v1/stock-opnames/{opn2['id']}/approve",
            headers=superadmin_user["auth_headers"],
        ).json()["status"]
        == "COMPLETED"
    )

    sa_audits = db_conn.execute(
        "SELECT action, details FROM audit_logs WHERE entity_type = 'stock_opnames' AND entity_id = %s AND action IN ('OPNAME_APPROVED_L1', 'OPNAME_APPROVED') ORDER BY id ASC",
        (str(opn2["id"]),),
    ).fetchall()
    assert len(sa_audits) == 2
    for row in sa_audits:
        det = json.loads(row["details"]) if isinstance(row["details"], str) else row["details"]
        assert det.get("sod_override") is True
