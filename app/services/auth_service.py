"""Service Autentikasi: login, refresh token rotation & reuse detection, logout, dan ganti password (FR-01, AC-11)."""

from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg import Connection

from app.core.config import settings
from app.core.exceptions import (
    AuthInvalidCredentials,
    AuthTokenInvalid,
    AuthTooManyAttempts,
    ValidationDomainError,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.repositories import token_repo, user_repo
from app.services import audit_service


def login(
    conn: Connection[dict[str, Any]],
    *,
    username: str,
    password: str,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Memproses login pengguna, mencatat kegagalan/penguncian akun, dan menerbitkan pasangan token."""
    now = datetime.now(timezone.utc)
    clean_username = username.strip()
    user = user_repo.get_user_by_username(conn, clean_username)

    # 1. Username tidak dikenali -> catat gagal login dengan user_id=None (FR-09)
    if not user:
        with conn.transaction():
            audit_service.record(
                conn,
                user_id=None,
                action="AUTH_LOGIN_FAILED",
                entity_type="users",
                entity_id=None,
                new_values={"username": clean_username, "reason": "UNKNOWN_USERNAME"},
                ip_address=ip_address,
            )
        raise AuthInvalidCredentials("Username atau kata sandi salah.")

    user_id = int(user["id"])
    error_to_raise: Exception | None = None
    result_tokens: dict[str, Any] = {}

    with conn.transaction():
        locked_user = user_repo.lock_user_by_id(conn, user_id)
        assert locked_user is not None

        locked_until: datetime | None = locked_user["locked_until"]
        if locked_until is not None and locked_until > now:
            audit_service.record(
                conn,
                user_id=user_id,
                action="AUTH_LOGIN_FAILED",
                entity_type="users",
                entity_id=user_id,
                new_values={
                    "username": username,
                    "reason": "ACCOUNT_LOCKED",
                    "locked_until": locked_until,
                },
                ip_address=ip_address,
            )
            error_to_raise = AuthTooManyAttempts(
                "Akun terkunci sementara akibat terlalu banyak percobaan login gagal.",
                details={"locked_until": locked_until.isoformat()},
            )
        elif not locked_user["is_active"]:
            audit_service.record(
                conn,
                user_id=user_id,
                action="AUTH_LOGIN_FAILED",
                entity_type="users",
                entity_id=user_id,
                new_values={"username": username, "reason": "USER_INACTIVE"},
                ip_address=ip_address,
            )
            error_to_raise = AuthInvalidCredentials("Username atau kata sandi salah.")
        elif not verify_password(password, locked_user["password_hash"]):
            # Jika sebelumnya sempat terkunci namun sudah lewat waktunya, mulai hitungan dari 1
            base_count = (
                0
                if (locked_until is not None and locked_until <= now)
                else int(locked_user["failed_login_count"])
            )
            new_count = base_count + 1
            new_locked_until: datetime | None = None
            if new_count >= settings.login_max_attempts:
                new_locked_until = now + timedelta(minutes=settings.login_lock_minutes)

            user_repo.update_login_failure(
                conn,
                user_id,
                failed_login_count=new_count,
                locked_until=new_locked_until,
            )
            audit_service.record(
                conn,
                user_id=user_id,
                action="AUTH_LOGIN_LOCKED" if new_locked_until else "AUTH_LOGIN_FAILED",
                entity_type="users",
                entity_id=user_id,
                new_values={
                    "username": username,
                    "reason": "INVALID_CREDENTIALS",
                    "failed_login_count": new_count,
                    "locked_until": new_locked_until,
                },
                ip_address=ip_address,
            )
            if new_locked_until is not None:
                error_to_raise = AuthTooManyAttempts(
                    "Akun dikunci selama 15 menit karena 5 kali gagal login berturut-turut.",
                    details={"locked_until": new_locked_until.isoformat()},
                )
            else:
                error_to_raise = AuthInvalidCredentials("Username atau kata sandi salah.")
        else:
            # Login berhasil: reset counter, terbitkan Access Token & Refresh Token
            user_repo.update_login_success(conn, user_id, last_login_at=now)
            access_token, access_exp = create_access_token(user_id)
            raw_refresh, refresh_hash, refresh_exp = generate_refresh_token()
            token_row = token_repo.insert_refresh_token(
                conn,
                user_id=user_id,
                token_hash=refresh_hash,
                expires_at=refresh_exp,
            )
            audit_service.record(
                conn,
                user_id=user_id,
                action="AUTH_LOGIN_SUCCESS",
                entity_type="users",
                entity_id=user_id,
                new_values={"refresh_token_id": token_row["id"]},
                ip_address=ip_address,
            )
            result_tokens = {
                "access_token": access_token,
                "refresh_token": raw_refresh,
                "token_type": "bearer",
                "expires_in": settings.access_token_minutes * 60,
                "access_expires_at": access_exp,
            }

    if error_to_raise is not None:
        raise error_to_raise

    return result_tokens


def refresh_session(
    conn: Connection[dict[str, Any]],
    *,
    refresh_token: str,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Merotasi Refresh Token; bila token yang sudah dicabut dipakai ulang, mencabut semua token aktif user (AC-11)."""
    now = datetime.now(timezone.utc)
    incoming_hash = hash_refresh_token(refresh_token)
    error_to_raise: Exception | None = None
    result_tokens: dict[str, Any] = {}

    with conn.transaction():
        token_row = token_repo.lock_refresh_token_by_hash(conn, incoming_hash)
        if not token_row:
            error_to_raise = AuthTokenInvalid("Refresh token tidak valid.")
        else:
            user_id = int(token_row["user_id"])
            token_id = int(token_row["id"])

            # Deteksi penggunaan ulang token yang sudah dicabut (FR-01 & AC-11)
            if token_row["revoked_at"] is not None:
                revoked_count = token_repo.update_revoke_all_user_tokens(
                    conn, user_id, revoked_at=now
                )
                audit_service.record(
                    conn,
                    user_id=user_id,
                    action="AUTH_REFRESH_TOKEN_REUSE_DETECTED",
                    entity_type="refresh_tokens",
                    entity_id=token_id,
                    new_values={
                        "reused_token_id": token_id,
                        "revoked_active_sessions": revoked_count,
                    },
                    ip_address=ip_address,
                )
                error_to_raise = AuthTokenInvalid(
                    "Refresh token sudah dicabut; seluruh sesi aktif telah dihentikan demi keamanan."
                )
            elif token_row["expires_at"] <= now:
                token_repo.update_revoke_and_replace_token(
                    conn, token_id, revoked_at=now, replaced_by_id=None
                )
                audit_service.record(
                    conn,
                    user_id=user_id,
                    action="AUTH_TOKEN_REFRESH_FAILED",
                    entity_type="refresh_tokens",
                    entity_id=token_id,
                    new_values={"reason": "TOKEN_EXPIRED"},
                    ip_address=ip_address,
                )
                error_to_raise = AuthTokenInvalid("Refresh token sudah kedaluwarsa.")
            else:
                user = user_repo.lock_user_by_id(conn, user_id)
                if not user or not user["is_active"]:
                    token_repo.update_revoke_all_user_tokens(conn, user_id, revoked_at=now)
                    audit_service.record(
                        conn,
                        user_id=user_id,
                        action="AUTH_TOKEN_REFRESH_FAILED",
                        entity_type="refresh_tokens",
                        entity_id=token_id,
                        new_values={"reason": "USER_INACTIVE"},
                        ip_address=ip_address,
                    )
                    error_to_raise = AuthTokenInvalid("Akun pengguna sudah tidak aktif.")
                else:
                    access_token, access_exp = create_access_token(user_id)
                    new_raw_refresh, new_refresh_hash, new_refresh_exp = (
                        generate_refresh_token()
                    )
                    new_token_row = token_repo.insert_refresh_token(
                        conn,
                        user_id=user_id,
                        token_hash=new_refresh_hash,
                        expires_at=new_refresh_exp,
                    )
                    token_repo.update_revoke_and_replace_token(
                        conn,
                        token_id,
                        revoked_at=now,
                        replaced_by_id=int(new_token_row["id"]),
                    )
                    audit_service.record(
                        conn,
                        user_id=user_id,
                        action="AUTH_TOKEN_REFRESHED",
                        entity_type="refresh_tokens",
                        entity_id=new_token_row["id"],
                        old_values={"previous_token_id": token_id},
                        new_values={"new_token_id": new_token_row["id"]},
                        ip_address=ip_address,
                    )
                    result_tokens = {
                        "access_token": access_token,
                        "refresh_token": new_raw_refresh,
                        "token_type": "bearer",
                        "expires_in": settings.access_token_minutes * 60,
                        "access_expires_at": access_exp,
                    }

    if error_to_raise is not None:
        raise error_to_raise

    return result_tokens


def logout(
    conn: Connection[dict[str, Any]],
    *,
    refresh_token: str,
    actor: dict[str, Any],
    ip_address: str | None = None,
) -> None:
    """Mencabut Refresh Token yang dipakai saat logout dan mencatatnya di Audit Log (FR-01, AC-11)."""
    now = datetime.now(timezone.utc)
    incoming_hash = hash_refresh_token(refresh_token)
    actor_id = int(actor["id"])

    with conn.transaction():
        token_row = token_repo.lock_refresh_token_by_hash(conn, incoming_hash)
        if not token_row or int(token_row["user_id"]) != actor_id:
            raise AuthTokenInvalid("Refresh token tidak valid untuk pengguna ini.")

        token_id = int(token_row["id"])
        if token_row["revoked_at"] is None:
            token_repo.update_revoke_and_replace_token(
                conn, token_id, revoked_at=now, replaced_by_id=None
            )

        audit_service.record(
            conn,
            user_id=actor_id,
            action="AUTH_LOGOUT",
            entity_type="refresh_tokens",
            entity_id=token_id,
            new_values={"revoked_token_id": token_id},
            ip_address=ip_address,
        )


def change_password(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    current_password: str,
    new_password: str,
    ip_address: str | None = None,
) -> None:
    """Mengganti kata sandi pengguna aktif dan mencabut seluruh Refresh Token miliknya (FR-01, PRD 7.2)."""
    if len(new_password) < 8:
        raise ValidationDomainError(
            "Kata sandi baru minimal harus terdiri dari 8 karakter."
        )

    actor_id = int(actor["id"])
    now = datetime.now(timezone.utc)

    with conn.transaction():
        locked_user = user_repo.lock_user_by_id(conn, actor_id)
        if not locked_user or not verify_password(
            current_password, locked_user["password_hash"]
        ):
            raise AuthInvalidCredentials("Kata sandi saat ini tidak sesuai.")

        new_hash = hash_password(new_password)
        user_repo.update_user_password(conn, actor_id, password_hash=new_hash)
        revoked_count = token_repo.update_revoke_all_user_tokens(
            conn, actor_id, revoked_at=now
        )
        audit_service.record(
            conn,
            user_id=actor_id,
            action="USER_PASSWORD_CHANGED",
            entity_type="users",
            entity_id=actor_id,
            new_values={"revoked_refresh_tokens": revoked_count},
            ip_address=ip_address,
        )
