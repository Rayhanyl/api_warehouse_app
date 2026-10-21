"""Repository SQL untuk tabel refresh_tokens (FR-01 & AC-11)."""

from datetime import datetime
from typing import Any

from psycopg import Connection


def insert_refresh_token(
    conn: Connection[dict[str, Any]],
    *,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> dict[str, Any]:
    """Menyimpan hash Refresh Token baru."""
    row = conn.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES (%s, %s, %s)
        RETURNING id, user_id, token_hash, expires_at, revoked_at, replaced_by_id, created_at
        """,
        (user_id, token_hash, expires_at),
    ).fetchone()
    assert row is not None
    return row


def lock_refresh_token_by_hash(
    conn: Connection[dict[str, Any]], token_hash: str
) -> dict[str, Any] | None:
    """Mengunci baris refresh_tokens berdasarkan token_hash (SELECT ... FOR UPDATE)."""
    return conn.execute(
        """
        SELECT
            id,
            user_id,
            token_hash,
            expires_at,
            revoked_at,
            replaced_by_id,
            created_at
        FROM refresh_tokens
        WHERE token_hash = %s
        FOR UPDATE
        """,
        (token_hash,),
    ).fetchone()


def update_revoke_and_replace_token(
    conn: Connection[dict[str, Any]],
    token_id: int,
    *,
    revoked_at: datetime,
    replaced_by_id: int | None = None,
) -> None:
    """Mencabut satu Refresh Token dan mencatat ID token penggantinya bila dirotasi."""
    conn.execute(
        """
        UPDATE refresh_tokens
        SET
            revoked_at = %s,
            replaced_by_id = %s
        WHERE id = %s
        """,
        (revoked_at, replaced_by_id, token_id),
    )


def update_revoke_all_user_tokens(
    conn: Connection[dict[str, Any]],
    user_id: int,
    *,
    revoked_at: datetime,
) -> int:
    """Mencabut seluruh Refresh Token aktif milik seorang pengguna (saat token reuse, ganti password, atau nonaktif)."""
    cur = conn.execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = %s
        WHERE user_id = %s AND revoked_at IS NULL
        """,
        (revoked_at, user_id),
    )
    return cur.rowcount or 0

