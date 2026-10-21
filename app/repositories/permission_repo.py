"""Repository SQL untuk roles, permissions, role_permissions, dan user_warehouses (Bagian 3 PRD)."""

from typing import Any

from psycopg import Connection


def list_roles(conn: Connection[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mengambil seluruh peran beserta daftar kode permission masing-masing."""
    rows = conn.execute(
        """
        SELECT
            r.id,
            r.name,
            r.description,
            r.created_at,
            r.updated_at,
            COALESCE(
                ARRAY(
                    SELECT p.code
                    FROM role_permissions rp
                    JOIN permissions p ON p.id = rp.permission_id
                    WHERE rp.role_id = r.id
                    ORDER BY p.code
                ),
                ARRAY[]::VARCHAR[]
            ) AS permissions
        FROM roles r
        ORDER BY r.id
        """
    ).fetchall()
    return list(rows)


def get_role_by_id(
    conn: Connection[dict[str, Any]], role_id: int
) -> dict[str, Any] | None:
    """Mengambil satu peran beserta daftar kode permission berdasarkan ID."""
    row = conn.execute(
        """
        SELECT
            r.id,
            r.name,
            r.description,
            r.created_at,
            r.updated_at,
            COALESCE(
                ARRAY(
                    SELECT p.code
                    FROM role_permissions rp
                    JOIN permissions p ON p.id = rp.permission_id
                    WHERE rp.role_id = r.id
                    ORDER BY p.code
                ),
                ARRAY[]::VARCHAR[]
            ) AS permissions
        FROM roles r
        WHERE r.id = %s
        """,
        (role_id,),
    ).fetchone()
    return row


def get_role_by_name(
    conn: Connection[dict[str, Any]], name: str
) -> dict[str, Any] | None:
    """Mengambil satu peran berdasarkan nama."""
    return conn.execute(
        """
        SELECT id, name, description, created_at, updated_at
        FROM roles
        WHERE name = %s
        """,
        (name,),
    ).fetchone()


def list_permissions(conn: Connection[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mengambil seluruh kode permission yang terdaftar di sistem."""
    rows = conn.execute(
        """
        SELECT id, code, description, created_at, updated_at
        FROM permissions
        ORDER BY id
        """
    ).fetchall()
    return list(rows)


def get_permissions_by_codes(
    conn: Connection[dict[str, Any]], codes: list[str]
) -> list[dict[str, Any]]:
    """Mengambil baris permissions berdasarkan daftar kode."""
    if not codes:
        return []
    rows = conn.execute(
        """
        SELECT id, code, description
        FROM permissions
        WHERE code = ANY(%s)
        ORDER BY code
        """,
        (codes,),
    ).fetchall()
    return list(rows)


def update_role_permissions(
    conn: Connection[dict[str, Any]],
    role_id: int,
    permission_ids: list[int],
) -> None:
    """Mengatur ulang pemetaan role_permissions untuk satu role."""
    conn.execute(
        "DELETE FROM role_permissions WHERE role_id = %s",
        (role_id,),
    )
    for perm_id in permission_ids:
        conn.execute(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (%s, %s)
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """,
            (role_id, perm_id),
        )
    conn.execute(
        "UPDATE roles SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (role_id,),
    )


def get_user_warehouse_ids(
    conn: Connection[dict[str, Any]], user_id: int
) -> list[int]:
    """Mengambil daftar ID gudang yang ditugaskan kepada pengguna."""
    rows = conn.execute(
        """
        SELECT warehouse_id
        FROM user_warehouses
        WHERE user_id = %s
        ORDER BY warehouse_id
        """,
        (user_id,),
    ).fetchall()
    return [int(r["warehouse_id"]) for r in rows]


def list_user_warehouses_detail(
    conn: Connection[dict[str, Any]], user_id: int
) -> list[dict[str, Any]]:
    """Mengambil detail gudang yang ditugaskan kepada seorang pengguna."""
    rows = conn.execute(
        """
        SELECT
            w.id AS warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            w.is_active,
            uw.created_by,
            uw.created_at
        FROM user_warehouses uw
        JOIN warehouses w ON w.id = uw.warehouse_id
        WHERE uw.user_id = %s
        ORDER BY w.id
        """,
        (user_id,),
    ).fetchall()
    return list(rows)


def get_existing_warehouses_by_ids(
    conn: Connection[dict[str, Any]], warehouse_ids: list[int]
) -> list[dict[str, Any]]:
    """Mengambil baris gudang berdasarkan daftar ID untuk memvalidasi penugasan gudang."""
    if not warehouse_ids:
        return []
    rows = conn.execute(
        """
        SELECT id, code, name, is_active
        FROM warehouses
        WHERE id = ANY(%s)
        ORDER BY id
        """,
        (warehouse_ids,),
    ).fetchall()
    return list(rows)


def update_user_warehouses(
    conn: Connection[dict[str, Any]],
    *,
    user_id: int,
    warehouse_ids: list[int],
    actor_id: int,
) -> list[int]:
    """Mengganti daftar penugasan gudang (user_warehouses) untuk seorang pengguna."""
    conn.execute(
        "DELETE FROM user_warehouses WHERE user_id = %s",
        (user_id,),
    )
    for wh_id in sorted(set(warehouse_ids)):
        conn.execute(
            """
            INSERT INTO user_warehouses (user_id, warehouse_id, created_by)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, warehouse_id) DO NOTHING
            """,
            (user_id, wh_id, actor_id),
        )
    return get_user_warehouse_ids(conn, user_id)

