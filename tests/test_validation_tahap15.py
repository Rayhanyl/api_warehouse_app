"""Pengujian menyeluruh validasi data backend dan respons 422 terstruktur (Tahap 15)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
import psycopg
import pytest

from app.core.exceptions import ValidationDomainError
from app.services import user_service
from tests import factories


def test_tahap15_pydantic_422_returns_indonesian_messages_and_field_errors(
    client: TestClient,
    superadmin_user: dict[str, Any],
) -> None:
    resp = client.post(
        "/api/v1/users",
        headers=superadmin_user["auth_headers"],
        json={
            "username": "bad user",
            "email": "bukan-email",
            "password": "   ",
            "full_name": "   ",
            "role_id": 0,
            "warehouse_ids": [-1],
        },
    )
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert "kesalahan validasi" in err["message"].lower()

    field_errors = err["details"]["field_errors"]
    assert "username" in field_errors
    assert "email" in field_errors
    assert "password" in field_errors
    assert "full_name" in field_errors
    assert "role_id" in field_errors
    assert "warehouse_ids" in field_errors

    # Pastikan nilai password tidak pernah dikembalikan di response error 422
    for item in err["details"]["errors"]:
        if item.get("field") == "password":
            assert "input" not in item


def test_tahap15_secret_inputs_not_leaked_in_422_response_or_audit_logs(
    client: TestClient,
    superadmin_user: dict[str, Any],
    db_conn: psycopg.Connection[dict[str, Any]],
) -> None:
    secret_pw = "RaHaSiA_S3cr3t!"
    resp = client.post(
        "/api/v1/auth/change-password",
        headers=superadmin_user["auth_headers"],
        json={
            "current_password": secret_pw,
            "new_password": "   ",
        },
    )
    assert resp.status_code == 422
    body_text = resp.text
    assert secret_pw not in body_text

    row = db_conn.execute(
        """
        SELECT action, new_values
        FROM audit_logs
        WHERE action = 'VALIDATION_ERROR'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    assert row is not None
    assert secret_pw not in str(row["new_values"])


def test_tahap15_blank_whitespace_and_format_validation_across_modules(
    client: TestClient,
    superadmin_user: dict[str, Any],
    db_conn: psycopg.Connection[dict[str, Any]],
) -> None:
    headers = superadmin_user["auth_headers"]
    wh = factories.create_warehouse(db_conn, code="WH-V15", name="Gudang V15")

    # Category whitespace-only name
    r_cat = client.post("/api/v1/categories", headers=headers, json={"name": "   "})
    assert r_cat.status_code == 422
    assert "name" in r_cat.json()["error"]["details"]["field_errors"]

    # UoM invalid code with space
    r_uom = client.post(
        "/api/v1/uoms",
        headers=headers,
        json={"code": "KG BAG", "name": "Kilogram"},
    )
    assert r_uom.status_code == 422
    assert "code" in r_uom.json()["error"]["details"]["field_errors"]

    # Supplier invalid phone & invalid email
    r_sup = client.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "code": "SUP-V15",
            "name": "Pemasok Uji",
            "phone": "123",
            "email": "salah-format",
        },
    )
    assert r_sup.status_code == 422
    sup_fields = r_sup.json()["error"]["details"]["field_errors"]
    assert "phone" in sup_fields
    assert "email" in sup_fields

    # Warehouse blank name
    r_wh = client.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"code": "WH-V15B", "name": "   "},
    )
    assert r_wh.status_code == 422
    assert "name" in r_wh.json()["error"]["details"]["field_errors"]

    # Storage location invalid code
    r_loc = client.post(
        f"/api/v1/warehouses/{wh['id']}/locations",
        headers=headers,
        json={"code": "-A01", "name": "Rak A1"},
    )
    assert r_loc.status_code == 422
    assert "code" in r_loc.json()["error"]["details"]["field_errors"]

    # Menu invalid path & non-kebab icon
    r_menu = client.post(
        "/api/v1/menus",
        headers=headers,
        json={
            "code": "menu-uji",
            "name": "Menu Uji",
            "path": "tanpa-slash",
            "icon": "PackageCheck",
        },
    )
    assert r_menu.status_code == 422
    menu_fields = r_menu.json()["error"]["details"]["field_errors"]
    assert "path" in menu_fields
    assert "icon" in menu_fields


def test_tahap15_user_update_rejects_blank_full_name_in_http_and_service(
    client: TestClient,
    superadmin_user: dict[str, Any],
    staff_user: dict[str, Any],
    db_conn: psycopg.Connection[dict[str, Any]],
) -> None:
    resp = client.patch(
        f"/api/v1/users/{staff_user['id']}",
        headers=superadmin_user["auth_headers"],
        json={"full_name": "   "},
    )
    assert resp.status_code == 422
    assert "full_name" in resp.json()["error"]["details"]["field_errors"]

    with pytest.raises(ValidationDomainError) as exc_info:
        user_service.update_user(
            db_conn,
            actor=superadmin_user,
            user_id=int(staff_user["id"]),
            full_name="   ",
        )
    assert exc_info.value.details.get("field") == "full_name"

    # Warehouse IDs tidak valid ditolak
    resp_wh = client.put(
        f"/api/v1/users/{staff_user['id']}/warehouses",
        headers=superadmin_user["auth_headers"],
        json={"warehouse_ids": [0]},
    )
    assert resp_wh.status_code == 422
    assert "warehouse_ids" in resp_wh.json()["error"]["details"]["field_errors"]


def test_tahap15_transaction_qty_bounds_and_nested_field_errors(
    client: TestClient,
    superadmin_user: dict[str, Any],
    db_conn: psycopg.Connection[dict[str, Any]],
) -> None:
    headers = superadmin_user["auth_headers"]
    wh = factories.create_warehouse(db_conn, code="WH-TX15", name="Gudang TX15")
    sup = factories.create_supplier(db_conn, code="SUP-TX15", name="Pemasok TX15")
    cat = factories.create_category(db_conn, name="Cat TX15")
    uom = factories.create_uom(db_conn, code="KG15", name="Kilogram", allow_decimal=True)
    item = factories.create_item(
        db_conn,
        sku="ITM-TX15",
        name="Barang TX15",
        category_id=int(cat["id"]),
        uom_id=int(uom["id"]),
    )

    # Lebih dari 4 angka desimal -> 422 dengan path lines.0.qty_ordered
    resp_5dec = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh["id"],
            "order_date": "2026-11-14",
            "lines": [{"item_id": item["id"], "qty_ordered": "1.12345"}],
        },
    )
    assert resp_5dec.status_code == 422
    fe_5dec = resp_5dec.json()["error"]["details"]["field_errors"]
    assert "lines.0.qty_ordered" in fe_5dec
    assert "4 angka di belakang koma" in fe_5dec["lines.0.qty_ordered"]

    # Qty <= 0 -> 422
    resp_zero = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh["id"],
            "order_date": "2026-11-14",
            "lines": [{"item_id": item["id"], "qty_ordered": "0"}],
        },
    )
    assert resp_zero.status_code == 422
    assert "lines.0.qty_ordered" in resp_zero.json()["error"]["details"]["field_errors"]

    # Qty melebihi MAX_QTY -> 422
    resp_max = client.post(
        "/api/v1/purchase-orders",
        headers=headers,
        json={
            "supplier_id": sup["id"],
            "warehouse_id": wh["id"],
            "order_date": "2026-11-14",
            "lines": [{"item_id": item["id"], "qty_ordered": "100000000000000.0000"}],
        },
    )
    assert resp_max.status_code == 422
    assert "lines.0.qty_ordered" in resp_max.json()["error"]["details"]["field_errors"]
