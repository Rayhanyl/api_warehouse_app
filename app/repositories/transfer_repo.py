"""Repository SQL untuk Stock Transfer (stock_transfers) dan barisnya (stock_transfer_lines) (FR-06, PRD 5.1, 6.7)."""

from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import Connection

_HEADER_SELECT = """
    SELECT
        st.id,
        st.transfer_number,
        st.source_warehouse_id,
        sw.code AS source_warehouse_code,
        sw.name AS source_warehouse_name,
        st.source_location_id,
        sl.code AS source_location_code,
        st.destination_warehouse_id,
        dw.code AS destination_warehouse_code,
        dw.name AS destination_warehouse_name,
        st.destination_location_id,
        dl.code AS destination_location_code,
        st.status,
        st.notes,
        (
            SELECT COUNT(*)::INT
            FROM stock_transfer_lines stl
            WHERE stl.transfer_id = st.id
        ) AS line_count,
        st.approved_by,
        st.approved_at,
        st.shipped_by,
        st.shipped_at,
        st.received_by,
        st.received_at,
        st.created_by,
        st.created_at,
        st.updated_at
    FROM stock_transfers st
    JOIN warehouses sw ON sw.id = st.source_warehouse_id
    JOIN storage_locations sl ON sl.id = st.source_location_id
    JOIN warehouses dw ON dw.id = st.destination_warehouse_id
    JOIN storage_locations dl ON dl.id = st.destination_location_id
"""


def list_transfers(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    scoped_warehouse_ids: list[int] | None = None,
    warehouse_id: int | None = None,
    source_warehouse_id: int | None = None,
    destination_warehouse_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    order_by_sql: str = "st.id DESC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar Transfer dengan filter, pencarian, dan pagination.

    `scoped_warehouse_ids` (Warehouse Staff) membatasi pada Transfer yang gudang asal ATAU tujuannya
    termasuk gudang yang ditugaskan (PRD 3.2 poin 5).
    """
    if scoped_warehouse_ids is not None and len(scoped_warehouse_ids) == 0:
        return [], 0

    conditions: list[str] = []
    params: list[Any] = []

    if scoped_warehouse_ids is not None:
        conditions.append(
            "(st.source_warehouse_id = ANY(%s) OR st.destination_warehouse_id = ANY(%s))"
        )
        params.extend([scoped_warehouse_ids, scoped_warehouse_ids])

    if warehouse_id is not None:
        conditions.append(
            "(st.source_warehouse_id = %s OR st.destination_warehouse_id = %s)"
        )
        params.extend([warehouse_id, warehouse_id])

    if source_warehouse_id is not None:
        conditions.append("st.source_warehouse_id = %s")
        params.append(source_warehouse_id)

    if destination_warehouse_id is not None:
        conditions.append("st.destination_warehouse_id = %s")
        params.append(destination_warehouse_id)

    if status is not None:
        conditions.append("st.status = %s")
        params.append(status)

    if date_from is not None:
        conditions.append("(st.created_at AT TIME ZONE 'UTC')::DATE >= %s")
        params.append(date_from)

    if date_to is not None:
        conditions.append("(st.created_at AT TIME ZONE 'UTC')::DATE <= %s")
        params.append(date_to)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append(
            "(st.transfer_number ILIKE %s OR COALESCE(st.notes, '') ILIKE %s)"
        )
        params.extend([kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM stock_transfers st
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


def list_transfer_lines(
    conn: Connection[dict[str, Any]], transfer_id: int
) -> list[dict[str, Any]]:
    """Mengambil seluruh baris Transfer beserta detail barang dan UoM, diurutkan item_id."""
    rows = conn.execute(
        """
        SELECT
            stl.id,
            stl.transfer_id,
            stl.item_id,
            i.sku AS item_sku,
            i.name AS item_name,
            i.uom_id,
            u.code AS uom_code,
            u.allow_decimal,
            stl.qty,
            stl.qty_received,
            CASE
                WHEN stl.qty_received IS NULL THEN NULL
                ELSE (stl.qty - stl.qty_received)::NUMERIC(18, 4)
            END AS qty_variance,
            stl.variance_reason,
            stl.created_by,
            stl.created_at,
            stl.updated_at
        FROM stock_transfer_lines stl
        JOIN items i ON i.id = stl.item_id
        JOIN uoms u ON u.id = i.uom_id
        WHERE stl.transfer_id = %s
        ORDER BY stl.item_id ASC, stl.id ASC
        """,
        (transfer_id,),
    ).fetchall()
    return list(rows)


def get_transfer_by_id(
    conn: Connection[dict[str, Any]], transfer_id: int
) -> dict[str, Any] | None:
    """Mengambil header Transfer beserta daftar barisnya."""
    header = conn.execute(
        f"""
        {_HEADER_SELECT}
        WHERE st.id = %s
        """,
        (transfer_id,),
    ).fetchone()
    if not header:
        return None

    lines = list_transfer_lines(conn, transfer_id)
    result = dict(header)
    result["line_count"] = len(lines)
    result["lines"] = lines
    return result


def lock_transfer_by_id(
    conn: Connection[dict[str, Any]], transfer_id: int
) -> dict[str, Any] | None:
    """Mengunci baris header stock_transfers dengan SELECT ... FOR UPDATE (PRD 6.5 langkah 1)."""
    return conn.execute(
        """
        SELECT
            id,
            transfer_number,
            source_warehouse_id,
            source_location_id,
            destination_warehouse_id,
            destination_location_id,
            status,
            notes,
            approved_by,
            approved_at,
            shipped_by,
            shipped_at,
            received_by,
            received_at,
            created_by,
            created_at,
            updated_at
        FROM stock_transfers
        WHERE id = %s
        FOR UPDATE
        """,
        (transfer_id,),
    ).fetchone()


def insert_transfer_header(
    conn: Connection[dict[str, Any]],
    *,
    transfer_number: str,
    source_warehouse_id: int,
    source_location_id: int,
    destination_warehouse_id: int,
    destination_location_id: int,
    notes: str | None,
    created_by: int,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO stock_transfers (
            transfer_number,
            source_warehouse_id, source_location_id,
            destination_warehouse_id, destination_location_id,
            status, notes, created_by
        )
        VALUES (%s, %s, %s, %s, %s, 'DRAFT', %s, %s)
        RETURNING id
        """,
        (
            transfer_number,
            source_warehouse_id,
            source_location_id,
            destination_warehouse_id,
            destination_location_id,
            notes,
            created_by,
        ),
    ).fetchone()
    assert row is not None
    return row


def update_transfer_lines(
    conn: Connection[dict[str, Any]],
    *,
    transfer_id: int,
    lines: list[dict[str, Any]],
    actor_id: int,
) -> None:
    """Mengganti seluruh baris Transfer (hanya dipanggil saat Transfer berstatus DRAFT)."""
    conn.execute(
        "DELETE FROM stock_transfer_lines WHERE transfer_id = %s", (transfer_id,)
    )
    for line in lines:
        conn.execute(
            """
            INSERT INTO stock_transfer_lines (transfer_id, item_id, qty, created_by)
            VALUES (%s, %s, %s, %s)
            """,
            (transfer_id, line["item_id"], line["qty"], actor_id),
        )


def update_transfer_draft_header(
    conn: Connection[dict[str, Any]],
    transfer_id: int,
    *,
    source_warehouse_id: int,
    source_location_id: int,
    destination_warehouse_id: int,
    destination_location_id: int,
    notes: str | None,
) -> None:
    conn.execute(
        """
        UPDATE stock_transfers
        SET
            source_warehouse_id = %s,
            source_location_id = %s,
            destination_warehouse_id = %s,
            destination_location_id = %s,
            notes = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (
            source_warehouse_id,
            source_location_id,
            destination_warehouse_id,
            destination_location_id,
            notes,
            transfer_id,
        ),
    )


def update_transfer_approved(
    conn: Connection[dict[str, Any]], transfer_id: int, *, approved_by: int
) -> None:
    conn.execute(
        """
        UPDATE stock_transfers
        SET
            status = 'APPROVED',
            approved_by = %s,
            approved_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (approved_by, transfer_id),
    )


def update_transfer_shipped(
    conn: Connection[dict[str, Any]], transfer_id: int, *, shipped_by: int
) -> None:
    conn.execute(
        """
        UPDATE stock_transfers
        SET
            status = 'SHIPPED',
            shipped_by = %s,
            shipped_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (shipped_by, transfer_id),
    )


def update_transfer_received(
    conn: Connection[dict[str, Any]], transfer_id: int, *, received_by: int
) -> None:
    conn.execute(
        """
        UPDATE stock_transfers
        SET
            status = 'RECEIVED',
            received_by = %s,
            received_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (received_by, transfer_id),
    )


def update_transfer_cancelled(
    conn: Connection[dict[str, Any]], transfer_id: int
) -> None:
    conn.execute(
        """
        UPDATE stock_transfers
        SET
            status = 'CANCELLED',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (transfer_id,),
    )


def update_transfer_line_received(
    conn: Connection[dict[str, Any]],
    *,
    line_id: int,
    qty_received: Decimal,
    variance_reason: str | None,
) -> None:
    """Mencatat qty_received dan alasan selisih pada baris Transfer saat penerimaan (PRD 6.7)."""
    conn.execute(
        """
        UPDATE stock_transfer_lines
        SET
            qty_received = %s,
            variance_reason = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (qty_received, variance_reason, line_id),
    )

