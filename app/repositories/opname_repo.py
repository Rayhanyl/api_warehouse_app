"""Repository SQL untuk Stock Opname, baris hitung fisik, dan pemeriksaan pembekuan lokasi (FR-07, PRD 5.1, 6.5, 6.6)."""

from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import Connection

_HEADER_SELECT = """
    SELECT
        so.id,
        so.opname_number,
        so.warehouse_id,
        w.code AS warehouse_code,
        w.name AS warehouse_name,
        so.location_id,
        sl.code AS location_code,
        sl.name AS location_name,
        so.status,
        so.notes,
        (
            SELECT COUNT(*)::INT
            FROM stock_opname_lines sol
            WHERE sol.opname_id = so.id
        ) AS line_count,
        so.started_at,
        so.started_by,
        so.submitted_at,
        so.submitted_by,
        so.approved_by,
        so.approved_at,
        so.rejection_reason,
        so.created_by,
        so.created_at,
        so.updated_at
    FROM stock_opnames so
    JOIN warehouses w ON w.id = so.warehouse_id
    LEFT JOIN storage_locations sl ON sl.id = so.location_id
"""


def get_active_opname_freezing_location(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int,
) -> dict[str, Any] | None:
    """Mengembalikan sesi Stock Opname aktif (IN_PROGRESS / WAITING_APPROVAL) yang membekukan lokasi ini.

    Lokasi dianggap dibekukan bila pada gudang tersebut terdapat sesi Opname berstatus
    IN_PROGRESS atau WAITING_APPROVAL dengan cakupan seluruh gudang (location_id IS NULL)
    atau cakupan spesifik lokasi tersebut (location_id = %s).
    """
    return conn.execute(
        """
        SELECT id, opname_number, warehouse_id, location_id, status
        FROM stock_opnames
        WHERE warehouse_id = %s
          AND (location_id IS NULL OR location_id = %s)
          AND status IN ('IN_PROGRESS', 'WAITING_APPROVAL')
        ORDER BY id
        LIMIT 1
        """,
        (warehouse_id, location_id),
    ).fetchone()


def is_location_frozen(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int,
) -> bool:
    """Memeriksa apakah lokasi sedang dibekukan oleh sesi Stock Opname aktif (PRD 6.6)."""
    return (
        get_active_opname_freezing_location(
            conn, warehouse_id=warehouse_id, location_id=location_id
        )
        is not None
    )


def get_active_overlapping_opname(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int | None,
    exclude_opname_id: int | None = None,
) -> dict[str, Any] | None:
    """Mencari sesi Opname aktif (IN_PROGRESS / WAITING_APPROVAL) yang tumpang tindih dengan cakupan (FR-07, PRD 5.1)."""
    if location_id is None:
        # Cakupan seluruh gudang berbenturan dengan sesi Opname aktif mana pun di gudang tersebut
        if exclude_opname_id is not None:
            return conn.execute(
                """
                SELECT id, opname_number, warehouse_id, location_id, status
                FROM stock_opnames
                WHERE warehouse_id = %s
                  AND status IN ('IN_PROGRESS', 'WAITING_APPROVAL')
                  AND id <> %s
                ORDER BY id
                LIMIT 1
                """,
                (warehouse_id, exclude_opname_id),
            ).fetchone()
        return conn.execute(
            """
            SELECT id, opname_number, warehouse_id, location_id, status
            FROM stock_opnames
            WHERE warehouse_id = %s
              AND status IN ('IN_PROGRESS', 'WAITING_APPROVAL')
            ORDER BY id
            LIMIT 1
            """,
            (warehouse_id,),
        ).fetchone()

    if exclude_opname_id is not None:
        return conn.execute(
            """
            SELECT id, opname_number, warehouse_id, location_id, status
            FROM stock_opnames
            WHERE warehouse_id = %s
              AND (location_id IS NULL OR location_id = %s)
              AND status IN ('IN_PROGRESS', 'WAITING_APPROVAL')
              AND id <> %s
            ORDER BY id
            LIMIT 1
            """,
            (warehouse_id, location_id, exclude_opname_id),
        ).fetchone()

    return get_active_opname_freezing_location(
        conn, warehouse_id=warehouse_id, location_id=location_id
    )


def lock_scope_locations_for_update(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int | None,
) -> list[dict[str, Any]]:
    """Mengunci lokasi dalam cakupan Opname dengan SELECT ... FOR UPDATE urut id ASC saat Opname dimulai (PRD 6.5)."""
    if location_id is not None:
        rows = conn.execute(
            """
            SELECT id, warehouse_id, code, name, is_active
            FROM storage_locations
            WHERE warehouse_id = %s AND id = %s
            ORDER BY id ASC
            FOR UPDATE
            """,
            (warehouse_id, location_id),
        ).fetchall()
        return list(rows)

    rows = conn.execute(
        """
        SELECT id, warehouse_id, code, name, is_active
        FROM storage_locations
        WHERE warehouse_id = %s AND is_active = TRUE
        ORDER BY id ASC
        FOR UPDATE
        """,
        (warehouse_id,),
    ).fetchall()
    return list(rows)


def lock_scope_balances_for_snapshot(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int | None,
) -> list[dict[str, Any]]:
    """Mengunci dan mengambil saldo stok pada cakupan Opname untuk snapshot qty_system, urut (warehouse_id, location_id, item_id) (PRD 6.5)."""
    if location_id is not None:
        rows = conn.execute(
            """
            SELECT
                ib.warehouse_id,
                ib.location_id,
                ib.item_id,
                ib.qty_on_hand
            FROM inventory_balances ib
            JOIN storage_locations sl ON sl.id = ib.location_id
            WHERE ib.warehouse_id = %s
              AND ib.location_id = %s
              AND sl.is_active = TRUE
            ORDER BY ib.warehouse_id ASC, ib.location_id ASC, ib.item_id ASC
            FOR SHARE OF ib
            """,
            (warehouse_id, location_id),
        ).fetchall()
        return list(rows)

    rows = conn.execute(
        """
        SELECT
            ib.warehouse_id,
            ib.location_id,
            ib.item_id,
            ib.qty_on_hand
        FROM inventory_balances ib
        JOIN storage_locations sl ON sl.id = ib.location_id
        WHERE ib.warehouse_id = %s
          AND sl.is_active = TRUE
        ORDER BY ib.warehouse_id ASC, ib.location_id ASC, ib.item_id ASC
        FOR SHARE OF ib
        """,
        (warehouse_id,),
    ).fetchall()
    return list(rows)


def get_balance_qty_on_hand(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int,
    item_id: int,
) -> Decimal:
    """Mengambil qty_on_hand saat ini untuk kombinasi (warehouse_id, location_id, item_id), atau 0 bila belum ada baris."""
    row = conn.execute(
        """
        SELECT qty_on_hand
        FROM inventory_balances
        WHERE warehouse_id = %s AND location_id = %s AND item_id = %s
        """,
        (warehouse_id, location_id, item_id),
    ).fetchone()
    if not row:
        return Decimal("0.0000")
    return Decimal(row["qty_on_hand"]).quantize(Decimal("0.0001"))


def list_opnames(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    scoped_warehouse_ids: list[int] | None = None,
    warehouse_id: int | None = None,
    location_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    order_by_sql: str = "so.id DESC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar sesi Stock Opname dengan filter, pencarian, dan pagination."""
    if scoped_warehouse_ids is not None and len(scoped_warehouse_ids) == 0:
        return [], 0

    conditions: list[str] = []
    params: list[Any] = []

    if scoped_warehouse_ids is not None:
        conditions.append("so.warehouse_id = ANY(%s)")
        params.append(scoped_warehouse_ids)

    if warehouse_id is not None:
        conditions.append("so.warehouse_id = %s")
        params.append(warehouse_id)

    if location_id is not None:
        conditions.append("so.location_id = %s")
        params.append(location_id)

    if status is not None:
        conditions.append("so.status = %s")
        params.append(status)

    if date_from is not None:
        conditions.append("(so.created_at AT TIME ZONE 'UTC')::DATE >= %s")
        params.append(date_from)

    if date_to is not None:
        conditions.append("(so.created_at AT TIME ZONE 'UTC')::DATE <= %s")
        params.append(date_to)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append(
            "(so.opname_number ILIKE %s OR COALESCE(so.notes, '') ILIKE %s)"
        )
        params.extend([kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM stock_opnames so
        {where_sql}
        """,
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        {_HEADER_SELECT}
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def list_opname_lines(
    conn: Connection[dict[str, Any]], opname_id: int
) -> list[dict[str, Any]]:
    """Mengambil seluruh baris Stock Opname beserta detail lokasi, barang, dan UoM, diurutkan (location_id, item_id)."""
    rows = conn.execute(
        """
        SELECT
            sol.id,
            sol.opname_id,
            sol.warehouse_id,
            sol.location_id,
            sl.code AS location_code,
            sl.name AS location_name,
            sol.item_id,
            i.sku AS item_sku,
            i.name AS item_name,
            i.uom_id,
            u.code AS uom_code,
            u.allow_decimal,
            sol.qty_system,
            sol.qty_physical,
            sol.qty_variance,
            sol.counted_by,
            sol.counted_at,
            sol.notes,
            sol.created_by,
            sol.created_at,
            sol.updated_at
        FROM stock_opname_lines sol
        JOIN storage_locations sl ON sl.id = sol.location_id
        JOIN items i ON i.id = sol.item_id
        JOIN uoms u ON u.id = i.uom_id
        WHERE sol.opname_id = %s
        ORDER BY sol.location_id ASC, sol.item_id ASC, sol.id ASC
        """,
        (opname_id,),
    ).fetchall()
    return list(rows)


def get_opname_by_id(
    conn: Connection[dict[str, Any]], opname_id: int
) -> dict[str, Any] | None:
    """Mengambil header Stock Opname beserta daftar barisnya."""
    header = conn.execute(
        f"""
        {_HEADER_SELECT}
        WHERE so.id = %s
        """,
        (opname_id,),
    ).fetchone()
    if not header:
        return None

    lines = list_opname_lines(conn, opname_id)
    result = dict(header)
    result["line_count"] = len(lines)
    result["lines"] = lines
    return result


def lock_opname_by_id(
    conn: Connection[dict[str, Any]], opname_id: int
) -> dict[str, Any] | None:
    """Mengunci baris header stock_opnames dengan SELECT ... FOR UPDATE (PRD 6.5 langkah 1)."""
    return conn.execute(
        """
        SELECT
            id,
            opname_number,
            warehouse_id,
            location_id,
            status,
            notes,
            started_at,
            started_by,
            submitted_at,
            submitted_by,
            approved_by,
            approved_at,
            rejection_reason,
            created_by,
            created_at,
            updated_at
        FROM stock_opnames
        WHERE id = %s
        FOR UPDATE
        """,
        (opname_id,),
    ).fetchone()


def insert_opname_header(
    conn: Connection[dict[str, Any]],
    *,
    opname_number: str,
    warehouse_id: int,
    location_id: int | None,
    notes: str | None,
    created_by: int,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO stock_opnames (
            opname_number, warehouse_id, location_id, status, notes, created_by
        )
        VALUES (%s, %s, %s, 'DRAFT', %s, %s)
        RETURNING id
        """,
        (opname_number, warehouse_id, location_id, notes, created_by),
    ).fetchone()
    assert row is not None
    return row


def update_opname_draft_header(
    conn: Connection[dict[str, Any]],
    opname_id: int,
    *,
    location_id: int | None,
    notes: str | None,
) -> None:
    conn.execute(
        """
        UPDATE stock_opnames
        SET
            location_id = %s,
            notes = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (location_id, notes, opname_id),
    )


def insert_snapshot_lines(
    conn: Connection[dict[str, Any]],
    *,
    opname_id: int,
    warehouse_id: int,
    snapshot_rows: list[dict[str, Any]],
    actor_id: int,
) -> None:
    """Menyimpan potret saldo (qty_system) saat sesi Opname dimulai (DRAFT -> IN_PROGRESS)."""
    for row in snapshot_rows:
        conn.execute(
            """
            INSERT INTO stock_opname_lines (
                opname_id, warehouse_id, location_id, item_id, qty_system, qty_physical, created_by
            )
            VALUES (%s, %s, %s, %s, %s, NULL, %s)
            ON CONFLICT (opname_id, location_id, item_id) DO NOTHING
            """,
            (
                opname_id,
                warehouse_id,
                int(row["location_id"]),
                int(row["item_id"]),
                row["qty_on_hand"],
                actor_id,
            ),
        )


def get_opname_line_by_id(
    conn: Connection[dict[str, Any]],
    *,
    opname_id: int,
    line_id: int,
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, opname_id, warehouse_id, location_id, item_id, qty_system, qty_physical, qty_variance
        FROM stock_opname_lines
        WHERE opname_id = %s AND id = %s
        """,
        (opname_id, line_id),
    ).fetchone()


def get_opname_line_by_loc_item(
    conn: Connection[dict[str, Any]],
    *,
    opname_id: int,
    location_id: int,
    item_id: int,
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT id, opname_id, warehouse_id, location_id, item_id, qty_system, qty_physical, qty_variance
        FROM stock_opname_lines
        WHERE opname_id = %s AND location_id = %s AND item_id = %s
        """,
        (opname_id, location_id, item_id),
    ).fetchone()


def insert_opname_counted_line(
    conn: Connection[dict[str, Any]],
    *,
    opname_id: int,
    warehouse_id: int,
    location_id: int,
    item_id: int,
    qty_system: Decimal,
    qty_physical: Decimal,
    counted_by: int,
    notes: str | None,
) -> dict[str, Any]:
    """Menambahkan baris barang baru yang ditemukan secara fisik dengan qty_system = 0 (atau saldo saat ini) (FR-07)."""
    row = conn.execute(
        """
        INSERT INTO stock_opname_lines (
            opname_id, warehouse_id, location_id, item_id,
            qty_system, qty_physical, counted_by, counted_at, notes, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
        RETURNING id
        """,
        (
            opname_id,
            warehouse_id,
            location_id,
            item_id,
            qty_system,
            qty_physical,
            counted_by,
            notes,
            counted_by,
        ),
    ).fetchone()
    assert row is not None
    return row


def update_opname_counted_line(
    conn: Connection[dict[str, Any]],
    *,
    line_id: int,
    qty_physical: Decimal,
    counted_by: int,
    notes: str | None,
) -> None:
    """Memperbarui hasil hitung fisik (qty_physical) pada baris Stock Opname."""
    conn.execute(
        """
        UPDATE stock_opname_lines
        SET
            qty_physical = %s,
            counted_by = %s,
            counted_at = CURRENT_TIMESTAMP,
            notes = COALESCE(%s, notes),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (qty_physical, counted_by, notes, line_id),
    )


def update_opname_started(
    conn: Connection[dict[str, Any]],
    opname_id: int,
    *,
    started_by: int,
) -> None:
    conn.execute(
        """
        UPDATE stock_opnames
        SET
            status = 'IN_PROGRESS',
            started_at = CURRENT_TIMESTAMP,
            started_by = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (started_by, opname_id),
    )


def update_opname_submitted(
    conn: Connection[dict[str, Any]],
    opname_id: int,
    *,
    submitted_by: int,
) -> None:
    conn.execute(
        """
        UPDATE stock_opnames
        SET
            status = 'WAITING_APPROVAL',
            submitted_at = CURRENT_TIMESTAMP,
            submitted_by = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (submitted_by, opname_id),
    )


def update_opname_completed(
    conn: Connection[dict[str, Any]],
    opname_id: int,
    *,
    approved_by: int,
) -> None:
    conn.execute(
        """
        UPDATE stock_opnames
        SET
            status = 'COMPLETED',
            approved_by = %s,
            approved_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (approved_by, opname_id),
    )


def update_opname_rejected(
    conn: Connection[dict[str, Any]],
    opname_id: int,
    *,
    rejection_reason: str,
) -> None:
    conn.execute(
        """
        UPDATE stock_opnames
        SET
            status = 'IN_PROGRESS',
            rejection_reason = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (rejection_reason, opname_id),
    )


def update_opname_cancelled(
    conn: Connection[dict[str, Any]],
    opname_id: int,
) -> None:
    conn.execute(
        """
        UPDATE stock_opnames
        SET
            status = 'CANCELLED',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (opname_id,),
    )
