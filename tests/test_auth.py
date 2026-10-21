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
