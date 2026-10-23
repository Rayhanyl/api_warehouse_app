"""Repository SQL untuk Purchase Order (purchase_orders) dan PO Lines (po_lines) (FR-04, PRD 5.1, 6.2)."""

from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import Connection


def list_purchase_orders(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    scoped_warehouse_ids: list[int] | None = None,
    warehouse_id: int | None = None,
    supplier_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    order_by_sql: str = "po.id DESC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar Purchase Order dengan filter, pencarian, dan pagination."""
    if scoped_warehouse_ids is not None and len(scoped_warehouse_ids) == 0:
        return [], 0

    conditions: list[str] = []
    params: list[Any] = []

    if scoped_warehouse_ids is not None:
        conditions.append("po.warehouse_id = ANY(%s)")
        params.append(scoped_warehouse_ids)

    if warehouse_id is not None:
        conditions.append("po.warehouse_id = %s")
        params.append(warehouse_id)

    if supplier_id is not None:
        conditions.append("po.supplier_id = %s")
        params.append(supplier_id)

    if status is not None:
        conditions.append("po.status = %s")
        params.append(status)

    if date_from is not None:
        conditions.append("po.order_date >= %s")
        params.append(date_from)

    if date_to is not None:
        conditions.append("po.order_date <= %s")
        params.append(date_to)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append(
            "(po.po_number ILIKE %s OR s.name ILIKE %s OR s.code ILIKE %s OR COALESCE(po.notes, '') ILIKE %s)"
        )
        params.extend([kw, kw, kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN warehouses w ON w.id = po.warehouse_id
        {where_sql}
        """,
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            po.id,
            po.po_number,
            po.supplier_id,
            s.code AS supplier_code,
            s.name AS supplier_name,
            po.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            po.status,
            po.order_date,
            po.notes,
            (
                SELECT COUNT(*)::INT
                FROM po_lines pl
                WHERE pl.po_id = po.id
            ) AS line_count,
            po.issued_at,
            po.issued_by,
            po.closed_reason,
            po.closed_at,
            po.closed_by,
            po.created_by,
            po.created_at,
            po.updated_at
        FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN warehouses w ON w.id = po.warehouse_id
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def list_po_lines(
    conn: Connection[dict[str, Any]], po_id: int
) -> list[dict[str, Any]]:
    """Mengambil seluruh baris PO beserta detail barang dan UoM, diurutkan berdasarkan id."""
    rows = conn.execute(
        """
        SELECT
            pl.id,
            pl.po_id,
            pl.item_id,
            i.sku AS item_sku,
            i.name AS item_name,
            i.is_active AS item_is_active,
            i.uom_id,
            u.code AS uom_code,
            u.allow_decimal,
            pl.qty_ordered,
            pl.qty_received,
            pl.notes,
            pl.created_by,
            pl.created_at,
            pl.updated_at
        FROM po_lines pl
        JOIN items i ON i.id = pl.item_id
        JOIN uoms u ON u.id = i.uom_id
        WHERE pl.po_id = %s
        ORDER BY pl.id ASC
        """,
        (po_id,),
    ).fetchall()
    return list(rows)


def get_po_by_id(
    conn: Connection[dict[str, Any]], po_id: int
) -> dict[str, Any] | None:
    """Mengambil header PO beserta daftar barisnya."""
    header = conn.execute(
        """
        SELECT
            po.id,
            po.po_number,
            po.supplier_id,
            s.code AS supplier_code,
            s.name AS supplier_name,
            s.is_active AS supplier_is_active,
            po.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            w.is_active AS warehouse_is_active,
            po.status,
            po.order_date,
            po.notes,
            po.issued_at,
            po.issued_by,
            po.closed_reason,
            po.closed_at,
            po.closed_by,
            po.created_by,
            po.created_at,
            po.updated_at
        FROM purchase_orders po
        JOIN suppliers s ON s.id = po.supplier_id
        JOIN warehouses w ON w.id = po.warehouse_id
        WHERE po.id = %s
        """,
        (po_id,),
    ).fetchone()
    if not header:
        return None

    lines = list_po_lines(conn, po_id)
    result = dict(header)
    result["line_count"] = len(lines)
    result["lines"] = lines
    return result


def lock_po_by_id(
    conn: Connection[dict[str, Any]], po_id: int
) -> dict[str, Any] | None:
    """Mengunci baris header purchase_orders dengan SELECT ... FOR UPDATE (PRD 6.5)."""
    return conn.execute(
        """
        SELECT
            id,
            po_number,
            supplier_id,
            warehouse_id,
            status,
            order_date,
            notes,
            issued_at,
            issued_by,
            closed_reason,
            closed_at,
            closed_by,
            created_by,
            created_at,
            updated_at
        FROM purchase_orders
        WHERE id = %s
        FOR UPDATE
        """,
        (po_id,),
    ).fetchone()


def lock_po_lines(
    conn: Connection[dict[str, Any]], po_id: int
) -> list[dict[str, Any]]:
    """Mengunci seluruh baris po_lines untuk PO terkait dengan SELECT ... FOR UPDATE diurutkan id."""
    rows = conn.execute(
        """
        SELECT
            id,
            po_id,
            item_id,
            qty_ordered,
            qty_received,
            notes,
            created_by,
            created_at,
            updated_at
        FROM po_lines
        WHERE po_id = %s
        ORDER BY id ASC
        FOR UPDATE
        """,
        (po_id,),
    ).fetchall()
    return list(rows)


def insert_po_header(
    conn: Connection[dict[str, Any]],
    *,
    po_number: str,
    supplier_id: int,
    warehouse_id: int,
    order_date: date,
    notes: str | None,
    created_by: int,
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO purchase_orders (
            po_number, supplier_id, warehouse_id, status, order_date, notes, created_by
        )
        VALUES (%s, %s, %s, 'DRAFT', %s, %s, %s)
        RETURNING id
        """,
        (po_number, supplier_id, warehouse_id, order_date, notes, created_by),
    ).fetchone()
    assert row is not None
    return row


def replace_po_lines(
    conn: Connection[dict[str, Any]],
    *,
    po_id: int,
    lines: list[dict[str, Any]],
    actor_id: int,
) -> None:
    """Mengganti daftar baris PO (hanya saat PO berstatus DRAFT)."""
    conn.execute("DELETE FROM po_lines WHERE po_id = %s", (po_id,))
    for line in lines:
        conn.execute(
            """
            INSERT INTO po_lines (
                po_id, item_id, qty_ordered, qty_received, notes, created_by
            )
            VALUES (%s, %s, %s, 0.0000, %s, %s)
            """,
            (
                po_id,
                line["item_id"],
                line["qty_ordered"],
                line.get("notes"),
                actor_id,
            ),
        )


def update_po_draft_header(
    conn: Connection[dict[str, Any]],
    po_id: int,
    *,
    supplier_id: int,
    warehouse_id: int,
    order_date: date,
    notes: str | None,
) -> None:
    conn.execute(
        """
        UPDATE purchase_orders
        SET
            supplier_id = %s,
            warehouse_id = %s,
            order_date = %s,
            notes = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (supplier_id, warehouse_id, order_date, notes, po_id),
    )


def update_po_issued(
    conn: Connection[dict[str, Any]],
    po_id: int,
    *,
    issued_by: int,
) -> None:
    conn.execute(
        """
        UPDATE purchase_orders
        SET
            status = 'ISSUED',
            issued_at = CURRENT_TIMESTAMP,
            issued_by = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (issued_by, po_id),
    )


def update_po_cancelled(
    conn: Connection[dict[str, Any]],
    po_id: int,
) -> None:
    conn.execute(
        """
        UPDATE purchase_orders
        SET
            status = 'CANCELLED',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (po_id,),
    )


def update_po_closed(
    conn: Connection[dict[str, Any]],
    po_id: int,
    *,
    closed_reason: str,
    closed_by: int,
) -> None:
    conn.execute(
        """
        UPDATE purchase_orders
        SET
            status = 'CLOSED',
            closed_reason = %s,
            closed_at = CURRENT_TIMESTAMP,
            closed_by = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (closed_reason, closed_by, po_id),
    )


def update_po_status(
    conn: Connection[dict[str, Any]],
    po_id: int,
    *,
    status: str,
) -> None:
    conn.execute(
        """
        UPDATE purchase_orders
        SET
            status = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (status, po_id),
    )


def add_po_line_received_qty(
    conn: Connection[dict[str, Any]],
    *,
    po_line_id: int,
    qty_added: Decimal,
) -> dict[str, Any]:
    row = conn.execute(
        """
        UPDATE po_lines
        SET
            qty_received = qty_received + %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id, po_id, item_id, qty_ordered, qty_received
        """,
        (qty_added, po_line_id),
    ).fetchone()
    assert row is not None
    return row


def has_draft_or_posted_gr_for_po(
    conn: Connection[dict[str, Any]], po_id: int
) -> bool:
    """Memeriksa apakah terdapat GR berstatus DRAFT atau POSTED pada PO ini (syarat cancel PO ISSUED, PRD 5.1)."""
    row = conn.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM goods_receipts
            WHERE po_id = %s
              AND status IN ('DRAFT', 'POSTED')
        ) AS has_gr
        """,
        (po_id,),
    ).fetchone()
    return bool(row and row["has_gr"])


def has_draft_gr_for_po(
    conn: Connection[dict[str, Any]], po_id: int
) -> bool:
    """Memeriksa apakah terdapat GR berstatus DRAFT pada PO ini (syarat close PO, PRD 5.1)."""
    row = conn.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM goods_receipts
            WHERE po_id = %s
              AND status = 'DRAFT'
        ) AS has_draft_gr
        """,
        (po_id,),
    ).fetchone()
    return bool(row and row["has_draft_gr"])

