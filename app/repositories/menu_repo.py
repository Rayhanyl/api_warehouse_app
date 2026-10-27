"""Repository SQL untuk tabel `menus` (FR-01, PRD Lampiran A & C)."""

from typing import Any

from psycopg import Connection

MENU_SELECT_COLUMNS = """
    m.id,
    m.code,
    m.name,
    m.path,
    m.icon,
    m.parent_id,
    pm.code AS parent_code,
    pm.name AS parent_name,
    m.sort_order,
    m.permission_id,
    p.code AS permission_code,
    m.is_active,
    m.created_by,
    m.created_at,
    m.updated_at
"""


def list_active_menus_ordered(
    conn: Connection[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mengambil seluruh menu aktif beserta kode permission-nya, terurut sort_order ASC, id ASC."""
    rows = conn.execute(
        f"""
        SELECT {MENU_SELECT_COLUMNS}
        FROM menus m
        LEFT JOIN menus pm ON pm.id = m.parent_id
        LEFT JOIN permissions p ON p.id = m.permission_id
        WHERE m.is_active = TRUE
        ORDER BY m.sort_order ASC, m.id ASC
        """
    ).fetchall()
    return list(rows)


def list_menus(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    is_active: bool | None,
    parent_id: int | None,
    search: str | None,
    order_by_sql: str,
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar menu terpaginasi untuk administrasi."""
    conditions: list[str] = []
    params: list[Any] = []

    if is_active is not None:
        conditions.append("m.is_active = %s")
        params.append(is_active)

    if parent_id is not None:
        conditions.append("m.parent_id = %s")
        params.append(parent_id)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append("(m.code ILIKE %s OR m.name ILIKE %s OR m.path ILIKE %s)")
        params.extend([kw, kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM menus m
        {where_sql}
        """,
        params,
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT {MENU_SELECT_COLUMNS}
        FROM menus m
        LEFT JOIN menus pm ON pm.id = m.parent_id
        LEFT JOIN permissions p ON p.id = m.permission_id
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        [*params, limit, offset],
    ).fetchall()
    return list(rows), total


def get_menu_by_id(
    conn: Connection[dict[str, Any]], menu_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        f"""
        SELECT {MENU_SELECT_COLUMNS}
        FROM menus m
        LEFT JOIN menus pm ON pm.id = m.parent_id
        LEFT JOIN permissions p ON p.id = m.permission_id
        WHERE m.id = %s
        """,
        (menu_id,),
    ).fetchone()


def lock_menu_by_id(
    conn: Connection[dict[str, Any]], menu_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            id,
            code,
            name,
            path,
            icon,
            parent_id,
            sort_order,
            permission_id,
            is_active,
            created_by,
            created_at,
            updated_at
        FROM menus
        WHERE id = %s
        FOR UPDATE
        """,
        (menu_id,),
    ).fetchone()


def get_menu_by_code(
    conn: Connection[dict[str, Any]], code: str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, code, name, is_active
        FROM menus
        WHERE code = %s
        """,
        (code,),
    ).fetchone()


def get_permission_by_id(
    conn: Connection[dict[str, Any]], permission_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        "SELECT id, code, description FROM permissions WHERE id = %s",
        (permission_id,),
    ).fetchone()


def has_active_child_menus(
    conn: Connection[dict[str, Any]], menu_id: int
) -> bool:
    row = conn.execute(
        """
        SELECT 1 AS in_use
        FROM menus
        WHERE parent_id = %s AND is_active = TRUE
        LIMIT 1
        """,
        (menu_id,),
    ).fetchone()
    return row is not None


def insert_menu(
    conn: Connection[dict[str, Any]],
    *,
    code: str,
    name: str,
    path: str,
    icon: str | None,
    parent_id: int | None,
    sort_order: int,
    permission_id: int | None,
    is_active: bool,
    created_by: int | None,
) -> dict[str, Any] | None:
    inserted = conn.execute(
        """
        INSERT INTO menus (
            code,
            name,
            path,
            icon,
            parent_id,
            sort_order,
            permission_id,
            is_active,
            created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (code) DO NOTHING
        RETURNING id
        """,
        (
            code,
            name,
            path,
            icon,
            parent_id,
            sort_order,
            permission_id,
            is_active,
            created_by,
        ),
    ).fetchone()
    if inserted is None:
        return None
    full_row = get_menu_by_id(conn, int(inserted["id"]))
    assert full_row is not None
    return full_row


def update_menu(
    conn: Connection[dict[str, Any]],
    menu_id: int,
    *,
    code: str,
    name: str,
    path: str,
    icon: str | None,
    parent_id: int | None,
    sort_order: int,
    permission_id: int | None,
    is_active: bool,
) -> dict[str, Any]:
    conn.execute(
        """
        UPDATE menus
        SET code = %s,
            name = %s,
            path = %s,
            icon = %s,
            parent_id = %s,
            sort_order = %s,
            permission_id = %s,
            is_active = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (
            code,
            name,
            path,
            icon,
            parent_id,
            sort_order,
            permission_id,
            is_active,
            menu_id,
        ),
    )
    full_row = get_menu_by_id(conn, menu_id)
    assert full_row is not None
    return full_row

