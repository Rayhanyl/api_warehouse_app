"""Repository SQL untuk Gudang (warehouses) dan Lokasi Penyimpanan (storage_locations) (FR-02, PRD 6.8)."""

from typing import Any

from psycopg import Connection


# ============================================================================
# Warehouses
# ============================================================================
def list_warehouses(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    is_active: bool | None = None,
    search: str | None = None,
    order_by_sql: str = "w.id ASC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar gudang dengan filter, pencarian, dan pagination."""
    conditions: list[str] = []
    params: list[Any] = []

    if is_active is not None:
        conditions.append("w.is_active = %s")
        params.append(is_active)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append(
            "(w.code ILIKE %s OR w.name ILIKE %s OR COALESCE(w.address, '') ILIKE %s)"
        )
        params.extend([kw, kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM warehouses w {where_sql}",
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            w.id,
            w.code,
            w.name,
            w.address,
            w.allow_negative_stock,
            w.is_active,
            w.created_by,
            w.created_at,
            w.updated_at
        FROM warehouses w
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def get_warehouse_by_id(
    conn: Connection[dict[str, Any]], warehouse_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            id, code, name, address, allow_negative_stock,
            is_active, created_by, created_at, updated_at
        FROM warehouses
        WHERE id = %s
        """,
        (warehouse_id,),
    ).fetchone()


def lock_warehouse_by_id(
    conn: Connection[dict[str, Any]], warehouse_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            id, code, name, address, allow_negative_stock,
            is_active, created_by, created_at, updated_at
        FROM warehouses
        WHERE id = %s
        FOR UPDATE
        """,
        (warehouse_id,),
    ).fetchone()


def get_warehouse_by_code(
    conn: Connection[dict[str, Any]], code: str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            id, code, name, address, allow_negative_stock,
            is_active, created_by, created_at, updated_at
        FROM warehouses
        WHERE LOWER(code) = LOWER(%s)
        """,
        (code,),
    ).fetchone()


def insert_warehouse(
    conn: Connection[dict[str, Any]],
    *,
    code: str,
    name: str,
    address: str | None,
    allow_negative_stock: bool,
    is_active: bool,
    created_by: int | None,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO warehouses (
            code, name, address, allow_negative_stock, is_active, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING
            id, code, name, address, allow_negative_stock,
            is_active, created_by, created_at, updated_at
        """,
        (code, name, address, allow_negative_stock, is_active, created_by),
    ).fetchone()
    assert row is not None
    return row


def update_warehouse(
    conn: Connection[dict[str, Any]],
    warehouse_id: int,
    *,
    code: str,
    name: str,
    address: str | None,
    allow_negative_stock: bool,
    is_active: bool,
) -> dict[str, Any]:
    row = conn.execute(
        """
        UPDATE warehouses
        SET
            code = %s,
            name = %s,
            address = %s,
            allow_negative_stock = %s,
            is_active = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING
            id, code, name, address, allow_negative_stock,
            is_active, created_by, created_at, updated_at
        """,
        (code, name, address, allow_negative_stock, is_active, warehouse_id),
    ).fetchone()
    assert row is not None
    return row


def is_warehouse_in_use(
    conn: Connection[dict[str, Any]], warehouse_id: int
) -> bool:
    """Memeriksa apakah gudang memiliki saldo != 0 atau masih dipakai pada dokumen belum final (PRD 6.8)."""
    row = conn.execute(
        """
        SELECT (
            EXISTS (
                SELECT 1 FROM inventory_balances
                WHERE warehouse_id = %s AND qty_on_hand <> 0
            )
            OR EXISTS (
                SELECT 1 FROM purchase_orders
                WHERE warehouse_id = %s
                  AND status IN ('DRAFT', 'ISSUED', 'PARTIALLY_RECEIVED')
            )
            OR EXISTS (
                SELECT 1 FROM goods_receipts
                WHERE warehouse_id = %s
                  AND status = 'DRAFT'
            )
            OR EXISTS (
                SELECT 1 FROM stock_transfers
                WHERE (source_warehouse_id = %s OR destination_warehouse_id = %s)
                  AND status IN ('DRAFT', 'APPROVED', 'SHIPPED')
            )
            OR EXISTS (
                SELECT 1 FROM stock_opnames
                WHERE warehouse_id = %s
                  AND status IN ('DRAFT', 'IN_PROGRESS', 'WAITING_APPROVAL')
            )
        ) AS in_use
        """,
        (
            warehouse_id,
            warehouse_id,
            warehouse_id,
            warehouse_id,
            warehouse_id,
            warehouse_id,
        ),
    ).fetchone()
    return bool(row and row["in_use"])


# ============================================================================
# Storage Locations
# ============================================================================
def list_locations(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    warehouse_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    order_by_sql: str = "sl.id ASC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar lokasi penyimpanan beserta kode & nama gudang."""
    conditions: list[str] = []
    params: list[Any] = []

    if warehouse_id is not None:
        conditions.append("sl.warehouse_id = %s")
        params.append(warehouse_id)

    if is_active is not None:
        conditions.append("sl.is_active = %s")
        params.append(is_active)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append("(sl.code ILIKE %s OR sl.name ILIKE %s)")
        params.extend([kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM storage_locations sl {where_sql}",
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            sl.id,
            sl.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            sl.code,
            sl.name,
            sl.is_active,
            sl.created_by,
            sl.created_at,
            sl.updated_at
        FROM storage_locations sl
        JOIN warehouses w ON w.id = sl.warehouse_id
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def get_location_by_id(
    conn: Connection[dict[str, Any]], location_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            sl.id,
            sl.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            sl.code,
            sl.name,
            sl.is_active,
            sl.created_by,
            sl.created_at,
            sl.updated_at
        FROM storage_locations sl
        JOIN warehouses w ON w.id = sl.warehouse_id
        WHERE sl.id = %s
        """,
        (location_id,),
    ).fetchone()


def lock_location_by_id(
    conn: Connection[dict[str, Any]], location_id: int
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT
            id, warehouse_id, code, name, is_active,
            created_by, created_at, updated_at
        FROM storage_locations
        WHERE id = %s
        FOR UPDATE
        """,
        (location_id,),
    ).fetchone()


def get_location_by_warehouse_and_code(
    conn: Connection[dict[str, Any]], warehouse_id: int, code: str
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, warehouse_id, code, name, is_active
        FROM storage_locations
        WHERE warehouse_id = %s AND LOWER(code) = LOWER(%s)
        """,
        (warehouse_id, code),
    ).fetchone()


def insert_location(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    code: str,
    name: str,
    is_active: bool,
    created_by: int | None,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO storage_locations (
            warehouse_id, code, name, is_active, created_by
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (warehouse_id, code, name, is_active, created_by),
    ).fetchone()
    assert row is not None
    detail = get_location_by_id(conn, int(row["id"]))
    assert detail is not None
    return detail


def update_location(
    conn: Connection[dict[str, Any]],
    location_id: int,
    *,
    code: str,
    name: str,
    is_active: bool,
) -> dict[str, Any]:
    conn.execute(
        """
        UPDATE storage_locations
        SET
            code = %s,
            name = %s,
            is_active = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (code, name, is_active, location_id),
    )
    detail = get_location_by_id(conn, location_id)
    assert detail is not None
    return detail


def is_location_in_use(
    conn: Connection[dict[str, Any]], location_id: int, warehouse_id: int
) -> bool:
    """Memeriksa apakah lokasi memiliki saldo != 0 atau masih dipakai pada dokumen belum final (PRD 6.8)."""
    row = conn.execute(
        """
        SELECT (
            EXISTS (
                SELECT 1 FROM inventory_balances
                WHERE location_id = %s AND qty_on_hand <> 0
            )
            OR EXISTS (
                SELECT 1
                FROM gr_lines gl
                JOIN goods_receipts gr ON gr.id = gl.gr_id
                WHERE gl.location_id = %s
                  AND gr.status = 'DRAFT'
            )
            OR EXISTS (
                SELECT 1 FROM stock_transfers
                WHERE (source_location_id = %s OR destination_location_id = %s)
                  AND status IN ('DRAFT', 'APPROVED', 'SHIPPED')
            )
            OR EXISTS (
                SELECT 1 FROM stock_opnames
                WHERE warehouse_id = %s
                  AND (location_id IS NULL OR location_id = %s)
                  AND status IN ('DRAFT', 'IN_PROGRESS', 'WAITING_APPROVAL')
            )
            OR EXISTS (
                SELECT 1
                FROM stock_opname_lines sol
                JOIN stock_opnames so ON so.id = sol.opname_id
                WHERE sol.location_id = %s
                  AND so.status IN ('DRAFT', 'IN_PROGRESS', 'WAITING_APPROVAL')
            )
        ) AS in_use
        """,
        (
            location_id,
            location_id,
            location_id,
            location_id,
            warehouse_id,
            location_id,
            location_id,
        ),
    ).fetchone()
    return bool(row and row["in_use"])

