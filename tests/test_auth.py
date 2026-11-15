"""Pengujian Autentikasi, Siklus Refresh Token (AC-11), dan Penguncian Akun (FR-01)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from psycopg import Connection


def test_ac11_refresh_token_rotation_reuse_detection_and_logout(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    staff_user: dict[str, Any],
) -> None:
    """AC-11 (Siklus Refresh Token):
    - Given pengguna memiliki Refresh Token R1 yang valid,
    - When R1 dipakai untuk memperbarui sesi, Then sistem menerbitkan token baru R2 dan R1 berstatus revoked.
    - When R1 dipakai lagi, Then sistem menolak (HTTP 401), mencabut seluruh Refresh Token aktif pengguna tersebut,
      dan mencatat kejadian pada Audit Log.
    - When pengguna melakukan logout, Then Refresh Token yang dipakai tidak dapat dipakai lagi.
    """
    # 1. Login pertama -> terbitkan R1
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": staff_user["username"], "password": staff_user["plain_password"]},
    )
    assert login_res.status_code == 200
    r1 = login_res.json()["refresh_token"]

    # 2. Gunakan R1 untuk refresh -> terbitkan R2, dan R1 otomatis berstatus revoked
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": r1})
    assert refresh_res.status_code == 200
    r2 = refresh_res.json()["refresh_token"]
    assert r2 != r1

    # 3. Gunakan ulang R1 yang sudah dicabut -> ditolak 401 AUTH_TOKEN_INVALID,
    #    R2 (seluruh token aktif user) ikut dicabut, dan tercatat di audit_logs!
    reuse_res = client.post("/api/v1/auth/refresh", json={"refresh_token": r1})
    assert reuse_res.status_code == 401
    assert reuse_res.json()["error"]["code"] == "AUTH_TOKEN_INVALID"

    # Pastikan R2 yang tadinya aktif kini ikut tercabut
    r2_res = client.post("/api/v1/auth/refresh", json={"refresh_token": r2})
    assert r2_res.status_code == 401
    assert r2_res.json()["error"]["code"] == "AUTH_TOKEN_INVALID"

    # Pastikan kejadian reuse tercatat di tabel audit_logs
    audit_row = db_conn.execute(
        """
        SELECT action, entity_type, user_id, new_values
        FROM audit_logs
        WHERE action = 'AUTH_REFRESH_TOKEN_REUSE_DETECTED' AND user_id = %s
        """,
        (staff_user["id"],),
    ).fetchone()
    assert audit_row is not None
    assert audit_row["entity_type"] == "refresh_tokens"

    # 4. Login kembali untuk menguji logout -> R3 dicabut dan tidak bisa dipakai lagi
    login2_res = client.post(
        "/api/v1/auth/login",
        json={"username": staff_user["username"], "password": staff_user["plain_password"]},
    )
    assert login2_res.status_code == 200
    tokens2 = login2_res.json()
    r3 = tokens2["refresh_token"]
    headers = {"Authorization": f"Bearer {tokens2['access_token']}"}

    logout_res = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": r3},
        headers=headers,
    )
    assert logout_res.status_code == 200

    after_logout_res = client.post("/api/v1/auth/refresh", json={"refresh_token": r3})
    assert after_logout_res.status_code == 401
    assert after_logout_res.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_login_lockout_after_5_failed_attempts_and_audit_log(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    staff_user: dict[str, Any],
) -> None:
    """FR-01: Lima kali kegagalan login berturut-turut mengunci akun selama 15 menit (HTTP 429 AUTH_TOO_MANY_ATTEMPTS)
    dan setiap kegagalan login tercatat pada Audit Log.
    """
    for attempt in range(1, 5):
        res = client.post(
            "/api/v1/auth/login",
            json={"username": staff_user["username"], "password": "WrongPassword!"},
        )
        assert res.status_code == 401, f"Percobaan ke-{attempt} harus 401"
        assert res.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    # Percobaan gagal ke-5 langsung mengunci akun (429 AUTH_TOO_MANY_ATTEMPTS)
    fifth_res = client.post(
        "/api/v1/auth/login",
        json={"username": staff_user["username"], "password": "WrongPassword!"},
    )
    assert fifth_res.status_code == 429
    assert fifth_res.json()["error"]["code"] == "AUTH_TOO_MANY_ATTEMPTS"

    # Saat terkunci, password yang benar sekalipun tetap ditolak 429
    locked_res = client.post(
        "/api/v1/auth/login",
        json={"username": staff_user["username"], "password": staff_user["plain_password"]},
    )
    assert locked_res.status_code == 429
    assert locked_res.json()["error"]["code"] == "AUTH_TOO_MANY_ATTEMPTS"

    # Pastikan seluruh kegagalan tercatat di audit_logs dan tidak ada password di dalam log
    logs = db_conn.execute(
        """
        SELECT action, new_values
        FROM audit_logs
        WHERE user_id = %s
        ORDER BY id
        """,
        (staff_user["id"],),
    ).fetchall()
    assert len(logs) == 6
    for row in logs:
        assert "WrongPassword!" not in str(row["new_values"])
        assert "password_hash" not in (row["new_values"] or {})


def test_ac11_cookie_httponly_refresh_rotation_and_cleanup(
    client: TestClient,
    staff_user: dict[str, Any],
) -> None:
    """AC-11, SEC-F01, CONF-008:
    - Login menetapkan cookie HttpOnly `refresh_token` dengan path /api/v1/auth.
    - Refresh token dapat dirotasi via cookie tanpa perlu menyertakan JSON body.
    - Logout menghapus cookie peramban dan mencabut sesi di database.
    """
    # 1. Login pertama -> periksa header Set-Cookie
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": staff_user["username"], "password": staff_user["plain_password"]},
    )
    assert login_res.status_code == 200
    assert "set-cookie" in login_res.headers
    cookie_header = login_res.headers["set-cookie"]
    assert "refresh_token=" in cookie_header
    assert "HttpOnly" in cookie_header or "httponly" in cookie_header
    assert "path=/api/v1/auth" in cookie_header.lower()

    first_cookie_val = client.cookies.get("refresh_token")
    assert first_cookie_val is not None

    # 2. Panggil refresh TANPA payload body -> rotasi sukses via cookie otomatis
    refresh_res = client.post("/api/v1/auth/refresh")
    assert refresh_res.status_code == 200
    rotated_data = refresh_res.json()
    assert "access_token" in rotated_data

    # Cookie terupdate dengan token baru
    rotated_cookie_val = client.cookies.get("refresh_token")
    assert rotated_cookie_val is not None
    assert rotated_cookie_val != first_cookie_val

    # 3. Logout -> cookie dihapus
    access_token = rotated_data["access_token"]
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_res.status_code == 200
    logout_cookie_header = logout_res.headers.get("set-cookie", "")
    assert 'refresh_token=""' in logout_cookie_header or "max-age=0" in logout_cookie_header.lower()

    # 4. Request refresh tanpa cookie/payload -> ditolak 401
    client.cookies.clear()
    unauth_refresh = client.post("/api/v1/auth/refresh")
    assert unauth_refresh.status_code == 401
    assert unauth_refresh.json()["error"]["code"] == "AUTH_TOKEN_INVALID"


def test_auth_me_returns_warehouse_scope_metadata(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    superadmin_user: dict[str, Any],
    staff_user: dict[str, Any],
    auditor_user: dict[str, Any],
) -> None:
    """Tahap 25: `/auth/me` memuat `has_all_warehouse_access` dan detail `warehouses`."""
    from app.repositories import permission_repo
    from tests import factories

    wh_a = factories.create_warehouse(db_conn, code="ME-WHA", name="Gudang Me A")
    wh_b = factories.create_warehouse(db_conn, code="ME-WHB", name="Gudang Me B")
    permission_repo.update_user_warehouses(
        db_conn, user_id=staff_user["id"], warehouse_ids=[wh_a["id"]], actor_id=superadmin_user["id"]
    )

    sa_res = client.get("/api/v1/auth/me", headers=superadmin_user["auth_headers"])
    assert sa_res.status_code == 200, sa_res.text
    sa_body = sa_res.json()
    assert sa_body["has_all_warehouse_access"] is True
    sa_wh_codes = {wh["code"] for wh in sa_body["warehouses"]}
    assert "ME-WHA" in sa_wh_codes
    assert "ME-WHB" in sa_wh_codes

    aud_res = client.get("/api/v1/auth/me", headers=auditor_user["auth_headers"])
    assert aud_res.status_code == 200, aud_res.text
    aud_body = aud_res.json()
    assert aud_body["has_all_warehouse_access"] is True
    assert "ME-WHA" in {wh["code"] for wh in aud_body["warehouses"]}

    staff_res = client.get("/api/v1/auth/me", headers=staff_user["auth_headers"])
    assert staff_res.status_code == 200, staff_res.text
    staff_body = staff_res.json()
    assert staff_body["has_all_warehouse_access"] is False
    assert staff_body["warehouse_ids"] == [wh_a["id"]]
    assert len(staff_body["warehouses"]) == 1
    assert staff_body["warehouses"][0]["id"] == wh_a["id"]
    assert staff_body["warehouses"][0]["code"] == "ME-WHA"
    assert staff_body["warehouses"][0]["name"] == "Gudang Me A"
    assert staff_body["warehouses"][0]["is_active"] is True


def test_normal_refresh_does_not_spam_audit_logs(
    client: TestClient,
    db_conn: Connection[dict[str, Any]],
    staff_user: dict[str, Any],
) -> None:
    """Tahap 26: Rotasi refresh token normal tidak menulis AUTH_TOKEN_REFRESHED ke audit_logs,
    namun kejadian keamanan (login, logout, gagal refresh, reuse) tetap dicatat.
    """
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": staff_user["username"], "password": staff_user["plain_password"]},
    )
    assert login_res.status_code == 200
    r1 = login_res.json()["refresh_token"]

    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": r1})
    assert refresh_res.status_code == 200

    refresh_logs = db_conn.execute(
        "SELECT id FROM audit_logs WHERE action = 'AUTH_TOKEN_REFRESHED' AND user_id = %s",
        (staff_user["id"],),
    ).fetchall()
    assert refresh_logs == []

    login_logs = db_conn.execute(
        "SELECT id FROM audit_logs WHERE action = 'AUTH_LOGIN_SUCCESS' AND user_id = %s",
        (staff_user["id"],),
    ).fetchall()
    assert len(login_logs) == 1

    bad_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not-a-valid-refresh-token-value"},
    )
    assert bad_refresh.status_code == 401
    failed_refresh_logs = db_conn.execute(
        "SELECT id FROM audit_logs WHERE action = 'AUTH_TOKEN_REFRESH_FAILED'"
    ).fetchall()
    assert len(failed_refresh_logs) >= 1
