"""Repository SQL untuk Goods Receipt (goods_receipts) dan GR Lines (gr_lines) (FR-05, PRD 5.1, 6.2)."""

from datetime import date
from typing import Any

from psycopg import Connection


def list_goods_receipts(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    scoped_warehouse_ids: list[int] | None = None,
    warehouse_id: int | None = None,
    po_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    order_by_sql: str = "gr.id DESC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar Goods Receipt dengan filter, pencarian, dan pagination."""
    if scoped_warehouse_ids is not None and len(scoped_warehouse_ids) == 0:
        return [], 0

    conditions: list[str] = []
    params: list[Any] = []

    if scoped_warehouse_ids is not None:
        conditions.append("gr.warehouse_id = ANY(%s)")
        params.append(scoped_warehouse_ids)

    if warehouse_id is not None:
        conditions.append("gr.warehouse_id = %s")
        params.append(warehouse_id)

    if po_id is not None:
        conditions.append("gr.po_id = %s")
        params.append(po_id)

    if status is not None:
        conditions.append("gr.status = %s")
        params.append(status)

    if date_from is not None:
        conditions.append("gr.received_date >= %s")
        params.append(date_from)

    if date_to is not None:
        conditions.append("gr.received_date <= %s")
        params.append(date_to)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append(
            "(gr.gr_number ILIKE %s OR po.po_number ILIKE %s OR s.name ILIKE %s OR COALESCE(gr.notes, '') ILIKE %s)"
        )
        params.extend([kw, kw, kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM goods_receipts gr
        JOIN purchase_orders po ON po.id = gr.po_id
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN warehouses w ON w.id = gr.warehouse_id
        {where_sql}
        """,
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            gr.id,
            gr.gr_number,
            gr.po_id,
            po.po_number,
            po.supplier_id,
            s.code AS supplier_code,
            s.name AS supplier_name,
            gr.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            gr.status,
            gr.received_date,
            gr.notes,
            (
                SELECT COUNT(*)::INT
                FROM gr_lines gl
                WHERE gl.gr_id = gr.id
            ) AS line_count,
            gr.posted_at,
            gr.posted_by,
            gr.created_by,
            gr.created_at,
            gr.updated_at
        FROM goods_receipts gr
        JOIN purchase_orders po ON po.id = gr.po_id
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN warehouses w ON w.id = gr.warehouse_id
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def list_gr_lines(
    conn: Connection[dict[str, Any]], gr_id: int
) -> list[dict[str, Any]]:
    """Mengambil seluruh baris GR beserta detail barang, UoM, dan lokasi penyimpanan."""
    rows = conn.execute(
        """
        SELECT
            gl.id,
            gl.gr_id,
            gl.po_id,
            gl.warehouse_id,
            gl.po_line_id,
            pl.item_id,
            i.sku AS item_sku,
            i.name AS item_name,
            i.is_active AS item_is_active,
            i.uom_id,
            u.code AS uom_code,
            u.allow_decimal,
            gl.location_id,
            sl.code AS location_code,
            sl.name AS location_name,
            sl.is_active AS location_is_active,
            gl.qty_received,
            gl.notes,
            gl.created_by,
            gl.created_at,
            gl.updated_at
        FROM gr_lines gl
        JOIN po_lines pl ON pl.id = gl.po_line_id
        JOIN items i ON i.id = pl.item_id
        JOIN uoms u ON u.id = i.uom_id
        JOIN storage_locations sl ON sl.id = gl.location_id
        WHERE gl.gr_id = %s
        ORDER BY gl.id ASC
        """,
        (gr_id,),
    ).fetchall()
    return list(rows)


def get_gr_by_id(
    conn: Connection[dict[str, Any]], gr_id: int
) -> dict[str, Any] | None:
    """Mengambil header GR beserta daftar barisnya."""
    header = conn.execute(
        """
        SELECT
            gr.id,
            gr.gr_number,
            gr.po_id,
            po.po_number,
            po.supplier_id,
            s.code AS supplier_code,
            s.name AS supplier_name,
            gr.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            gr.status,
            gr.received_date,
            gr.notes,
            gr.posted_at,
            gr.posted_by,
            gr.created_by,
            gr.created_at,
            gr.updated_at
        FROM goods_receipts gr
        JOIN purchase_orders po ON po.id = gr.po_id
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN warehouses w ON w.id = gr.warehouse_id
        WHERE gr.id = %s
        """,
        (gr_id,),
    ).fetchone()
    if not header:
        return None

    lines = list_gr_lines(conn, gr_id)
    result = dict(header)
    result["line_count"] = len(lines)
    result["lines"] = lines
    return result


def lock_gr_by_id(
    conn: Connection[dict[str, Any]], gr_id: int
) -> dict[str, Any] | None:
    """Mengunci baris header goods_receipts dengan SELECT ... FOR UPDATE (PRD 6.5)."""
    return conn.execute(
        """
        SELECT
            id,
            gr_number,
            po_id,
            warehouse_id,
            status,
            received_date,
            notes,
            posted_at,
            posted_by,
            created_by,
            created_at,
            updated_at
        FROM goods_receipts
        WHERE id = %s
        FOR UPDATE
        """,
        (gr_id,),
    ).fetchone()


def insert_gr_header(
    conn: Connection[dict[str, Any]],
    *,
    gr_number: str,
    po_id: int,
    warehouse_id: int,
    received_date: date,
    notes: str | None,
    created_by: int,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO goods_receipts (
            gr_number, po_id, warehouse_id, status, received_date, notes, created_by
        )
        VALUES (%s, %s, %s, 'DRAFT', %s, %s, %s)
        RETURNING id
        """,
        (gr_number, po_id, warehouse_id, received_date, notes, created_by),
    ).fetchone()
    assert row is not None
    return row


def replace_gr_lines(
    conn: Connection[dict[str, Any]],
    *,
    gr_id: int,
    po_id: int,
    warehouse_id: int,
    lines: list[dict[str, Any]],
    actor_id: int,
) -> None:
    """Mengganti daftar baris GR (hanya saat GR berstatus DRAFT)."""
    conn.execute("DELETE FROM gr_lines WHERE gr_id = %s", (gr_id,))
    for line in lines:
        conn.execute(
            """
            INSERT INTO gr_lines (
                gr_id, po_id, warehouse_id, po_line_id, location_id, qty_received, notes, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                gr_id,
                po_id,
                warehouse_id,
                line["po_line_id"],
                line["location_id"],
                line["qty_received"],
                line.get("notes"),
                actor_id,
            ),
        )


def update_gr_draft_header(
    conn: Connection[dict[str, Any]],
    gr_id: int,
    *,
    received_date: date,
    notes: str | None,
) -> None:
    conn.execute(
        """
        UPDATE goods_receipts
        SET
            received_date = %s,
            notes = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (received_date, notes, gr_id),
    )


def mark_gr_posted(
    conn: Connection[dict[str, Any]],
    gr_id: int,
    *,
    posted_by: int,
) -> None:
    conn.execute(
        """
        UPDATE goods_receipts
        SET
            status = 'POSTED',
            posted_at = CURRENT_TIMESTAMP,
            posted_by = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (posted_by, gr_id),
    )


def mark_gr_cancelled(
    conn: Connection[dict[str, Any]],
    gr_id: int,
) -> None:
    conn.execute(
        """
        UPDATE goods_receipts
        SET
            status = 'CANCELLED',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (gr_id,),
    )

