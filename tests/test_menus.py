"""Pengujian menu navigasi dinamis (AC-14)."""

from typing import Any

from fastapi.testclient import TestClient
import psycopg


def _permission_id(db_conn: psycopg.Connection[dict[str, Any]], code: str) -> int:
    row = db_conn.execute(
        "SELECT id FROM permissions WHERE code = %s",
        (code,),
    ).fetchone()
    assert row is not None
    return int(row["id"])


def _find_menu(nodes: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    for node in nodes:
        if node["code"] == code:
            return node
        found = _find_menu(node["children"], code)
        if found is not None:
            return found
    return None


def test_ac14_menu_tree_filters_permissions_and_keeps_visible_parents(
    client: TestClient,
    db_conn: psycopg.Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    purchasing_user: dict[str, Any],
    auditor_user: dict[str, Any],
) -> None:
    """Menu permission-filtered; parent hanya tampak bila ada anak yang terlihat."""
    parent = client.post(
        "/api/v1/menus",
        headers=superadmin_user["auth_headers"],
        json={
            "code": "ac14_menu_group",
            "name": "AC14 Group",
            "path": "/ac14",
            "sort_order": 900,
        },
    )
    assert parent.status_code == 201, parent.text
    parent_id = parent.json()["id"]

    allowed_child = client.post(
        "/api/v1/menus",
        headers=superadmin_user["auth_headers"],
        json={
            "code": "ac14_menu_allowed",
            "name": "Allowed",
            "path": "/ac14/allowed",
            "parent_id": parent_id,
            "sort_order": 20,
            "permission_id": _permission_id(db_conn, "master:manage"),
        },
    )
    hidden_child = client.post(
        "/api/v1/menus",
        headers=superadmin_user["auth_headers"],
        json={
            "code": "ac14_menu_hidden",
            "name": "Hidden",
            "path": "/ac14/hidden",
            "parent_id": parent_id,
            "sort_order": 30,
            "permission_id": _permission_id(db_conn, "user:manage"),
        },
    )
    earlier_child = client.post(
        "/api/v1/menus",
        headers=superadmin_user["auth_headers"],
        json={
            "code": "ac14_menu_earlier",
            "name": "Earlier",
            "path": "/ac14/earlier",
            "parent_id": parent_id,
            "sort_order": 10,
            "permission_id": _permission_id(db_conn, "master:manage"),
        },
    )
    assert allowed_child.status_code == 201, allowed_child.text
    assert hidden_child.status_code == 201, hidden_child.text
    assert earlier_child.status_code == 201, earlier_child.text

    purchasing_response = client.get(
        "/api/v1/menus/my-menu",
        headers=purchasing_user["auth_headers"],
    )
    assert purchasing_response.status_code == 200, purchasing_response.text
    purchasing_tree = purchasing_response.json()
    visible_parent = _find_menu(purchasing_tree, "ac14_menu_group")
    assert visible_parent is not None
    assert [node["code"] for node in visible_parent["children"]] == [
        "ac14_menu_earlier",
        "ac14_menu_allowed",
    ]
    assert _find_menu(purchasing_tree, "ac14_menu_hidden") is None
    assert _find_menu(purchasing_tree, "dashboard") is not None

    auditor_response = client.get(
        "/api/v1/menus/my-menu",
        headers=auditor_user["auth_headers"],
    )
    assert auditor_response.status_code == 200, auditor_response.text
    auditor_tree = auditor_response.json()
    assert _find_menu(auditor_tree, "ac14_menu_group") is None
    assert _find_menu(auditor_tree, "ac14_menu_allowed") is None
    assert _find_menu(auditor_tree, "dashboard") is not None


def test_ac14_menu_admin_permission_crud_and_audit_log(
    client: TestClient,
    db_conn: psycopg.Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    staff_user: dict[str, Any],
) -> None:
    """Administrasi menu dibatasi user:manage dan perubahan dicatat pada audit log."""
    forbidden = client.get(
        "/api/v1/menus",
        headers=staff_user["auth_headers"],
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "PERMISSION_DENIED"

    payload = {
        "code": "ac14_admin_menu",
        "name": "Admin Menu",
        "path": "/ac14/admin",
        "permission_id": _permission_id(db_conn, "user:manage"),
    }
    created = client.post(
        "/api/v1/menus",
        headers=superadmin_user["auth_headers"],
        json=payload,
    )
    assert created.status_code == 201, created.text
    menu_id = created.json()["id"]

    duplicate = client.post(
        "/api/v1/menus",
        headers=superadmin_user["auth_headers"],
        json=payload,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE"

    updated = client.patch(
        f"/api/v1/menus/{menu_id}",
        headers=superadmin_user["auth_headers"],
        json={"name": "Updated Admin Menu", "clear_permission": True},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Updated Admin Menu"
    assert updated.json()["permission_id"] is None

    audit_rows = db_conn.execute(
        """
        SELECT action, old_values, new_values
        FROM audit_logs
        WHERE entity_type = 'menus' AND entity_id = %s
        ORDER BY id
        """,
        (str(menu_id),),
    ).fetchall()
    assert [row["action"] for row in audit_rows] == [
        "MENU_CREATED",
        "MENU_UPDATED",
    ]
    assert audit_rows[0]["new_values"]["code"] == "ac14_admin_menu"
    assert audit_rows[1]["old_values"]["name"] == "Admin Menu"
    assert audit_rows[1]["new_values"]["name"] == "Updated Admin Menu"


def test_ac14_menu_parent_validation_and_soft_deactivation(
    client: TestClient,
    superadmin_user: dict[str, Any],
) -> None:
    parent_response = client.post(
        "/api/v1/menus",
        headers=superadmin_user["auth_headers"],
        json={
            "code": "ac14_parent_validation",
            "name": "Parent",
            "path": "/ac14/parent",
        },
    )
    assert parent_response.status_code == 201, parent_response.text
    parent_id = parent_response.json()["id"]

    child_response = client.post(
        "/api/v1/menus",
        headers=superadmin_user["auth_headers"],
        json={
            "code": "ac14_child_validation",
            "name": "Child",
            "path": "/ac14/parent/child",
            "parent_id": parent_id,
        },
    )
    assert child_response.status_code == 201, child_response.text
    child_id = child_response.json()["id"]

    cycle = client.patch(
        f"/api/v1/menus/{parent_id}",
        headers=superadmin_user["auth_headers"],
        json={"parent_id": child_id},
    )
    assert cycle.status_code == 422
    assert cycle.json()["error"]["code"] == "VALIDATION_ERROR"

    deactivate_parent = client.patch(
        f"/api/v1/menus/{parent_id}",
        headers=superadmin_user["auth_headers"],
        json={"is_active": False},
    )
    assert deactivate_parent.status_code == 409
    assert deactivate_parent.json()["error"]["code"] == "ENTITY_IN_USE"

    deactivate_child = client.patch(
        f"/api/v1/menus/{child_id}",
        headers=superadmin_user["auth_headers"],
        json={"is_active": False},
    )
    assert deactivate_child.status_code == 200, deactivate_child.text
    assert deactivate_child.json()["is_active"] is False
