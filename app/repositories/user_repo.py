"""Repository SQL untuk tabel users (FR-01, Bagian 3 PRD)."""

from datetime import datetime
from typing import Any

from psycopg import Connection

from app.utils.pagination import build_order_by

USER_SORT_COLUMNS: dict[str, str] = {
    "id": "u.id",
    "username": "u.username",
    "email": "u.email",
    "full_name": "u.full_name",
    "created_at": "u.created_at",
}


def get_user_by_id(
    conn: Connection[dict[str, Any]], user_id: int
) -> dict[str, Any] | None:
    """Mengambil data pengguna beserta nama role berdasarkan ID."""
    return conn.execute(
        """
        SELECT
            u.id,
            u.username,
            u.email,
            u.password_hash,
            u.full_name,
            u.role_id,
            r.name AS role_name,
            u.is_active,
            u.failed_login_count,
            u.locked_until,
            u.last_login_at,
            u.created_by,
            u.created_at,
            u.updated_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s
        """,
        (user_id,),
    ).fetchone()


def get_user_by_username(
    conn: Connection[dict[str, Any]], username: str
) -> dict[str, Any] | None:
    """Mengambil data pengguna beserta nama role berdasarkan username."""
    return conn.execute(
        """
        SELECT
            u.id,
            u.username,
            u.email,
            u.password_hash,
            u.full_name,
            u.role_id,
            r.name AS role_name,
            u.is_active,
            u.failed_login_count,
            u.locked_until,
            u.last_login_at,
            u.created_by,
            u.created_at,
            u.updated_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.username = %s
        """,
        (username,),
    ).fetchone()


def get_user_by_email(
    conn: Connection[dict[str, Any]], email: str
) -> dict[str, Any] | None:
    """Mengambil data pengguna berdasarkan email."""
    return conn.execute(
        """
        SELECT id, username, email
        FROM users
        WHERE email = %s
        """,
        (email,),
    ).fetchone()


def lock_user_by_id(
    conn: Connection[dict[str, Any]], user_id: int
) -> dict[str, Any] | None:
    """Mengunci baris pengguna (SELECT ... FOR UPDATE) berdasarkan ID."""
    return conn.execute(
        """
        SELECT
            u.id,
            u.username,
            u.email,
            u.password_hash,
            u.full_name,
            u.role_id,
            u.is_active,
            u.failed_login_count,
            u.locked_until,
            u.last_login_at,
            u.created_by,
            u.created_at,
            u.updated_at
        FROM users u
        WHERE u.id = %s
        FOR UPDATE
        """,
        (user_id,),
    ).fetchone()


def get_user_auth_context(
    conn: Connection[dict[str, Any]], user_id: int
) -> dict[str, Any] | None:
    """Mengambil profil lengkap pengguna, role, daftar permission, dan warehouse_ids dari DB pada setiap request (FR-01)."""
    user = get_user_by_id(conn, user_id)
    if not user:
        return None

    perm_rows = conn.execute(
        """
        SELECT p.code
        FROM role_permissions rp
        JOIN permissions p ON p.id = rp.permission_id
        WHERE rp.role_id = %s
        ORDER BY p.code
        """,
        (user["role_id"],),
    ).fetchall()

    wh_rows = conn.execute(
        """
        SELECT uw.warehouse_id
        FROM user_warehouses uw
        WHERE uw.user_id = %s
        ORDER BY uw.warehouse_id
        """,
        (user_id,),
    ).fetchall()

    user["permissions"] = [r["code"] for r in perm_rows]
    user["warehouse_ids"] = [int(r["warehouse_id"]) for r in wh_rows]
    return user


def list_users(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    role_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar pengguna dengan filter, pencarian teks, dan pagination."""
    conditions: list[str] = []
    params: list[Any] = []

    if role_id is not None:
        conditions.append("u.role_id = %s")
        params.append(role_id)
    if is_active is not None:
        conditions.append("u.is_active = %s")
        params.append(is_active)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            "(u.username ILIKE %s OR u.full_name ILIKE %s OR u.email ILIKE %s)"
        )
        params.extend([pattern, pattern, pattern])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_clause = build_order_by(sort_by, sort_dir, USER_SORT_COLUMNS, "id", "ASC")

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM users u {where_clause}",
        params,
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            u.id,
            u.username,
            u.email,
            u.full_name,
            u.role_id,
            r.name AS role_name,
            u.is_active,
            u.failed_login_count,
            u.locked_until,
            u.last_login_at,
            u.created_by,
            u.created_at,
            u.updated_at,
            COALESCE(
                ARRAY(
                    SELECT uw.warehouse_id
                    FROM user_warehouses uw
                    WHERE uw.user_id = u.id
                    ORDER BY uw.warehouse_id
                ),
                ARRAY[]::BIGINT[]
            ) AS warehouse_ids
        FROM users u
        JOIN roles r ON r.id = u.role_id
        {where_clause}
        ORDER BY {order_clause}
        LIMIT %s OFFSET %s
        """,
        [*params, limit, offset],
    ).fetchall()

    return list(rows), total


def insert_user(
    conn: Connection[dict[str, Any]],
    *,
    username: str,
    email: str,
    password_hash: str,
    full_name: str,
    role_id: int,
    is_active: bool = True,
    created_by: int | None = None,
) -> dict[str, Any]:
    """Menyisipkan pengguna baru ke tabel users."""
    row = conn.execute(
        """
        INSERT INTO users (
            username,
            email,
            password_hash,
            full_name,
            role_id,
            is_active,
            created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (username, email, password_hash, full_name, role_id, is_active, created_by),
    ).fetchone()
    assert row is not None
    created = get_user_auth_context(conn, int(row["id"]))
    assert created is not None
    return created


def update_user(
    conn: Connection[dict[str, Any]],
    user_id: int,
    *,
    email: str,
    full_name: str,
    role_id: int,
    is_active: bool,
) -> dict[str, Any]:
    """Memperbarui profil, role, atau status aktif pengguna."""
    conn.execute(
        """
        UPDATE users
        SET
            email = %s,
            full_name = %s,
            role_id = %s,
            is_active = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (email, full_name, role_id, is_active, user_id),
    )
    updated = get_user_auth_context(conn, user_id)
    assert updated is not None
    return updated


def update_user_password(
    conn: Connection[dict[str, Any]],
    user_id: int,
    *,
    password_hash: str,
) -> None:
    """Memperbarui password_hash pengguna dan mereset hitungan gagal login."""
    conn.execute(
        """
        UPDATE users
        SET
            password_hash = %s,
            failed_login_count = 0,
            locked_until = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (password_hash, user_id),
    )


def update_login_failure(
    conn: Connection[dict[str, Any]],
    user_id: int,
    *,
    failed_login_count: int,
    locked_until: datetime | None,
) -> None:
    """Memperbarui jumlah kegagalan login berturut-turut dan waktu penguncian akun."""
    conn.execute(
        """
        UPDATE users
        SET
            failed_login_count = %s,
            locked_until = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (failed_login_count, locked_until, user_id),
    )


def update_login_success(
    conn: Connection[dict[str, Any]],
    user_id: int,
    *,
    last_login_at: datetime,
) -> None:
    """Mereset kegagalan login dan mencatat waktu login terakhir yang berhasil."""
    conn.execute(
        """
        UPDATE users
        SET
            failed_login_count = 0,
            locked_until = NULL,
            last_login_at = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (last_login_at, user_id),
    )

