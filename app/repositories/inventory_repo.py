"""Repository SQL untuk saldo stok (inventory_balances) dan buku besar (stock_movements) (FR-03, FR-08, PRD 6.1, 6.5)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from psycopg import Connection


# ============================================================================
# Locking & Mutasi Saldo + Ledger (Dipanggil HANYA oleh inventory_service.apply_movement)
# ============================================================================
def lock_location_for_share(
    conn: Connection[dict[str, Any]], location_id: int
) -> dict[str, Any] | None:
    """Mengunci baris lokasi dengan FOR SHARE untuk pemeriksaan validitas & pembekuan Opname (PRD 6.5)."""
    return conn.execute(
        """
        SELECT
            sl.id,
            sl.warehouse_id,
            sl.code,
            sl.name,
            sl.is_active,
            w.code AS warehouse_code,
            w.is_active AS warehouse_is_active,
            w.allow_negative_stock
        FROM storage_locations sl
        JOIN warehouses w ON w.id = sl.warehouse_id
        WHERE sl.id = %s
        FOR SHARE OF sl
        """,
        (location_id,),
    ).fetchone()


def get_item_with_uom(
    conn: Connection[dict[str, Any]], item_id: int
) -> dict[str, Any] | None:
    """Mengambil informasi barang beserta atribut allow_decimal dari UoM dasarnya."""
    return conn.execute(
        """
        SELECT
            i.id,
            i.sku,
            i.name,
            i.is_active,
            i.uom_id,
            u.code AS uom_code,
            u.allow_decimal
        FROM items i
        JOIN uoms u ON u.id = i.uom_id
        WHERE i.id = %s
        """,
        (item_id,),
    ).fetchone()


def ensure_balance_row(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int,
    item_id: int,
    actor_id: int,
) -> None:
    """Membuat baris saldo awal 0 bila belum ada (INSERT ... ON CONFLICT DO NOTHING) sebelum dikunci FOR UPDATE (PRD 6.5)."""
    conn.execute(
        """
        INSERT INTO inventory_balances (
            warehouse_id, location_id, item_id, qty_on_hand, created_by
        )
        VALUES (%s, %s, %s, 0.0000, %s)
        ON CONFLICT (warehouse_id, location_id, item_id) DO NOTHING
        """,
        (warehouse_id, location_id, item_id, actor_id),
    )


def lock_balance_row(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int,
    item_id: int,
) -> dict[str, Any]:
    """Mengunci baris inventory_balances dengan SELECT ... FOR UPDATE (PRD 6.5)."""
    row = conn.execute(
        """
        SELECT
            id,
            warehouse_id,
            location_id,
            item_id,
            qty_on_hand,
            created_by,
            created_at,
            updated_at
        FROM inventory_balances
        WHERE warehouse_id = %s
          AND location_id = %s
          AND item_id = %s
        FOR UPDATE
        """,
        (warehouse_id, location_id, item_id),
    ).fetchone()
    assert row is not None
    return row


def update_balance_qty(
    conn: Connection[dict[str, Any]],
    *,
    balance_id: int,
    qty_after: Decimal,
) -> dict[str, Any]:
    """Memperbarui qty_on_hand pada inventory_balances (HANYA dipanggil dari inventory_service.apply_movement)."""
    row = conn.execute(
        """
        UPDATE inventory_balances
        SET
            qty_on_hand = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id, warehouse_id, location_id, item_id, qty_on_hand, updated_at
        """,
        (qty_after, balance_id),
    ).fetchone()
    assert row is not None
    return row


def insert_stock_movement(
    conn: Connection[dict[str, Any]],
    *,
    movement_type: str,
    warehouse_id: int,
    location_id: int,
    item_id: int,
    qty_before: Decimal,
    qty_change: Decimal,
    qty_after: Decimal,
    reference_type: str,
    reference_id: int,
    notes: str | None,
    created_by: int,
) -> dict[str, Any]:
    """Menulis baris baru ke stock_movements (append-only, FR-08)."""
    row = conn.execute(
        """
        INSERT INTO stock_movements (
            movement_type,
            warehouse_id,
            location_id,
            item_id,
            qty_before,
            qty_change,
            qty_after,
            reference_type,
            reference_id,
            notes,
            created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            id,
            movement_type,
            warehouse_id,
            location_id,
            item_id,
            qty_before,
            qty_change,
            qty_after,
            reference_type,
            reference_id,
            notes,
            created_by,
            created_at
        """,
        (
            movement_type,
            warehouse_id,
            location_id,
            item_id,
            qty_before,
            qty_change,
            qty_after,
            reference_type,
            reference_id,
            notes,
            created_by,
        ),
    ).fetchone()
    assert row is not None
    return row


# ============================================================================
# Query Pembacaan Stok & In-Transit (FR-03)
# ============================================================================
def list_stock_by_location(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    scoped_warehouse_ids: list[int] | None = None,
    warehouse_id: int | None = None,
    location_id: int | None = None,
    item_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    order_by_sql: str = "cb.warehouse_id ASC, cb.location_id ASC, cb.item_id ASC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil saldo stok aktual dan in-transit per kombinasi (gudang, lokasi, barang)."""
    if scoped_warehouse_ids is not None and len(scoped_warehouse_ids) == 0:
        return [], 0

    conditions: list[str] = []
    params: list[Any] = []

    if scoped_warehouse_ids is not None:
        conditions.append("cb.warehouse_id = ANY(%s)")
        params.append(scoped_warehouse_ids)

    if warehouse_id is not None:
        conditions.append("cb.warehouse_id = %s")
        params.append(warehouse_id)

    if location_id is not None:
        conditions.append("cb.location_id = %s")
        params.append(location_id)

    if item_id is not None:
        conditions.append("cb.item_id = %s")
        params.append(item_id)

    if category_id is not None:
        conditions.append("i.category_id = %s")
        params.append(category_id)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append("(i.sku ILIKE %s OR i.name ILIKE %s)")
        params.extend([kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cte_sql = """
        WITH in_transit_loc AS (
            SELECT
                st.destination_warehouse_id AS warehouse_id,
                st.destination_location_id AS location_id,
                stl.item_id,
                SUM(stl.qty)::NUMERIC(18, 4) AS qty_in_transit
            FROM stock_transfer_lines stl
            JOIN stock_transfers st ON st.id = stl.transfer_id
            WHERE st.status = 'SHIPPED'
            GROUP BY st.destination_warehouse_id, st.destination_location_id, stl.item_id
        ),
        cb AS (
            SELECT
                COALESCE(ib.warehouse_id, it.warehouse_id) AS warehouse_id,
                COALESCE(ib.location_id, it.location_id) AS location_id,
                COALESCE(ib.item_id, it.item_id) AS item_id,
                COALESCE(ib.qty_on_hand, 0.0000)::NUMERIC(18, 4) AS qty_on_hand,
                COALESCE(it.qty_in_transit, 0.0000)::NUMERIC(18, 4) AS qty_in_transit,
                ib.updated_at
            FROM inventory_balances ib
            FULL OUTER JOIN in_transit_loc it
                ON ib.warehouse_id = it.warehouse_id
               AND ib.location_id = it.location_id
               AND ib.item_id = it.item_id
        )
    """

    count_row = conn.execute(
        f"""
        {cte_sql}
        SELECT COUNT(*) AS total
        FROM cb
        JOIN warehouses w ON w.id = cb.warehouse_id
        JOIN storage_locations sl ON sl.id = cb.location_id
        JOIN items i ON i.id = cb.item_id
        JOIN categories c ON c.id = i.category_id
        JOIN uoms u ON u.id = i.uom_id
        {where_sql}
        """,
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        {cte_sql}
        SELECT
            cb.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            cb.location_id,
            sl.code AS location_code,
            sl.name AS location_name,
            cb.item_id,
            i.sku AS item_sku,
            i.name AS item_name,
            i.category_id,
            c.name AS category_name,
            i.uom_id,
            u.code AS uom_code,
            cb.qty_on_hand,
            cb.qty_in_transit,
            cb.updated_at
        FROM cb
        JOIN warehouses w ON w.id = cb.warehouse_id
        JOIN storage_locations sl ON sl.id = cb.location_id
        JOIN items i ON i.id = cb.item_id
        JOIN categories c ON c.id = i.category_id
        JOIN uoms u ON u.id = i.uom_id
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def list_stock_by_warehouse(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    scoped_warehouse_ids: list[int] | None = None,
    warehouse_id: int | None = None,
    item_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    order_by_sql: str = "cb.warehouse_id ASC, cb.item_id ASC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil saldo stok dan in-transit yang diagregasi pada tingkat gudang per barang."""
    if scoped_warehouse_ids is not None and len(scoped_warehouse_ids) == 0:
        return [], 0

    conditions: list[str] = []
    params: list[Any] = []

    if scoped_warehouse_ids is not None:
        conditions.append("cb.warehouse_id = ANY(%s)")
        params.append(scoped_warehouse_ids)

    if warehouse_id is not None:
        conditions.append("cb.warehouse_id = %s")
        params.append(warehouse_id)

    if item_id is not None:
        conditions.append("cb.item_id = %s")
        params.append(item_id)

    if category_id is not None:
        conditions.append("i.category_id = %s")
        params.append(category_id)

    if search:
        kw = f"%{search.strip()}%"
        conditions.append("(i.sku ILIKE %s OR i.name ILIKE %s)")
        params.extend([kw, kw])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cte_sql = """
        WITH wh_balance AS (
            SELECT
                ib.warehouse_id,
                ib.item_id,
                SUM(ib.qty_on_hand)::NUMERIC(18, 4) AS qty_on_hand
            FROM inventory_balances ib
            GROUP BY ib.warehouse_id, ib.item_id
        ),
        in_transit_wh AS (
            SELECT
                st.destination_warehouse_id AS warehouse_id,
                stl.item_id,
                SUM(stl.qty)::NUMERIC(18, 4) AS qty_in_transit
            FROM stock_transfer_lines stl
            JOIN stock_transfers st ON st.id = stl.transfer_id
            WHERE st.status = 'SHIPPED'
            GROUP BY st.destination_warehouse_id, stl.item_id
        ),
        cb AS (
            SELECT
                COALESCE(wb.warehouse_id, it.warehouse_id) AS warehouse_id,
                COALESCE(wb.item_id, it.item_id) AS item_id,
                COALESCE(wb.qty_on_hand, 0.0000)::NUMERIC(18, 4) AS qty_on_hand,
                COALESCE(it.qty_in_transit, 0.0000)::NUMERIC(18, 4) AS qty_in_transit
            FROM wh_balance wb
            FULL OUTER JOIN in_transit_wh it
                ON wb.warehouse_id = it.warehouse_id
               AND wb.item_id = it.item_id
        )
    """

    count_row = conn.execute(
        f"""
        {cte_sql}
        SELECT COUNT(*) AS total
        FROM cb
        JOIN warehouses w ON w.id = cb.warehouse_id
        JOIN items i ON i.id = cb.item_id
        JOIN categories c ON c.id = i.category_id
        JOIN uoms u ON u.id = i.uom_id
        {where_sql}
        """,
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        {cte_sql}
        SELECT
            cb.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            cb.item_id,
            i.sku AS item_sku,
            i.name AS item_name,
            i.category_id,
            c.name AS category_name,
            i.uom_id,
            u.code AS uom_code,
            cb.qty_on_hand,
            cb.qty_in_transit
        FROM cb
        JOIN warehouses w ON w.id = cb.warehouse_id
        JOIN items i ON i.id = cb.item_id
        JOIN categories c ON c.id = i.category_id
        JOIN uoms u ON u.id = i.uom_id
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total


def list_stock_summary(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    scoped_warehouse_ids: list[int] | None = None,
    warehouse_id: int | None = None,
    item_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    order_by_sql: str = "cb.item_id ASC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil saldo stok dan in-transit agregat lintas gudang per barang."""
    if scoped_warehouse_ids is not None and len(scoped_warehouse_ids) == 0:
        return [], 0

    bal_conditions: list[str] = []
    bal_params: list[Any] = []
    trf_conditions: list[str] = ["st.status = 'SHIPPED'"]
    trf_params: list[Any] = []

    if scoped_warehouse_ids is not None:
        bal_conditions.append("ib.warehouse_id = ANY(%s)")
        bal_params.append(scoped_warehouse_ids)
        trf_conditions.append("st.destination_warehouse_id = ANY(%s)")
        trf_params.append(scoped_warehouse_ids)

    if warehouse_id is not None:
        bal_conditions.append("ib.warehouse_id = %s")
        bal_params.append(warehouse_id)
        trf_conditions.append("st.destination_warehouse_id = %s")
        trf_params.append(warehouse_id)

    bal_where = f"WHERE {' AND '.join(bal_conditions)}" if bal_conditions else ""
    trf_where = f"WHERE {' AND '.join(trf_conditions)}"

    outer_conditions: list[str] = []
    outer_params: list[Any] = []

    if item_id is not None:
        outer_conditions.append("cb.item_id = %s")
        outer_params.append(item_id)

    if category_id is not None:
        outer_conditions.append("i.category_id = %s")
        outer_params.append(category_id)

    if search:
        kw = f"%{search.strip()}%"
        outer_conditions.append("(i.sku ILIKE %s OR i.name ILIKE %s)")
        outer_params.extend([kw, kw])

    outer_where = f"WHERE {' AND '.join(outer_conditions)}" if outer_conditions else ""

    cte_sql = f"""
        WITH item_balance AS (
            SELECT
                ib.item_id,
                SUM(ib.qty_on_hand)::NUMERIC(18, 4) AS qty_on_hand
            FROM inventory_balances ib
            {bal_where}
            GROUP BY ib.item_id
        ),
        item_in_transit AS (
            SELECT
                stl.item_id,
                SUM(stl.qty)::NUMERIC(18, 4) AS qty_in_transit
            FROM stock_transfer_lines stl
            JOIN stock_transfers st ON st.id = stl.transfer_id
            {trf_where}
            GROUP BY stl.item_id
        ),
        cb AS (
            SELECT
                COALESCE(b.item_id, it.item_id) AS item_id,
                COALESCE(b.qty_on_hand, 0.0000)::NUMERIC(18, 4) AS qty_on_hand,
                COALESCE(it.qty_in_transit, 0.0000)::NUMERIC(18, 4) AS qty_in_transit
            FROM item_balance b
            FULL OUTER JOIN item_in_transit it ON b.item_id = it.item_id
        )
    """

    all_filter_params = [*bal_params, *trf_params, *outer_params]

    count_row = conn.execute(
        f"""
        {cte_sql}
        SELECT COUNT(*) AS total
        FROM cb
        JOIN items i ON i.id = cb.item_id
        JOIN categories c ON c.id = i.category_id
        JOIN uoms u ON u.id = i.uom_id
        {outer_where}
        """,
        tuple(all_filter_params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        {cte_sql}
        SELECT
            cb.item_id,
            i.sku AS item_sku,
            i.name AS item_name,
            i.category_id,
            c.name AS category_name,
            i.uom_id,
            u.code AS uom_code,
            cb.qty_on_hand,
            cb.qty_in_transit
        FROM cb
        JOIN items i ON i.id = cb.item_id
        JOIN categories c ON c.id = i.category_id
        JOIN uoms u ON u.id = i.uom_id
        {outer_where}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*all_filter_params, limit, offset]),
    ).fetchall()
    return list(rows), total


# ============================================================================
# Query Buku Besar Pergerakan Stok / Ledger (FR-08 & FR-11)
# ============================================================================
def list_stock_movements(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    scoped_warehouse_ids: list[int] | None = None,
    warehouse_id: int | None = None,
    location_id: int | None = None,
    item_id: int | None = None,
    movement_type: str | None = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    order_by_sql: str = "sm.id DESC",
) -> tuple[list[dict[str, Any]], int]:
    """Mengambil daftar riwayat pergerakan stok (Stock Movement Ledger) dengan filter & pagination."""
    if scoped_warehouse_ids is not None and len(scoped_warehouse_ids) == 0:
        return [], 0

    conditions: list[str] = []
    params: list[Any] = []

    if scoped_warehouse_ids is not None:
        conditions.append("sm.warehouse_id = ANY(%s)")
        params.append(scoped_warehouse_ids)

    if warehouse_id is not None:
        conditions.append("sm.warehouse_id = %s")
        params.append(warehouse_id)

    if location_id is not None:
        conditions.append("sm.location_id = %s")
        params.append(location_id)

    if item_id is not None:
        conditions.append("sm.item_id = %s")
        params.append(item_id)

    if movement_type is not None:
        conditions.append("sm.movement_type = %s")
        params.append(movement_type)

    if reference_type is not None:
        conditions.append("sm.reference_type = %s")
        params.append(reference_type)

    if reference_id is not None:
        conditions.append("sm.reference_id = %s")
        params.append(reference_id)

    if date_from is not None:
        conditions.append("sm.created_at >= %s")
        params.append(date_from)

    if date_to is not None:
        conditions.append("sm.created_at <= %s")
        params.append(date_to)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM stock_movements sm {where_sql}",
        tuple(params),
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            sm.id,
            sm.movement_type,
            sm.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            sm.location_id,
            sl.code AS location_code,
            sl.name AS location_name,
            sm.item_id,
            i.sku AS item_sku,
            i.name AS item_name,
            u.code AS uom_code,
            sm.qty_before,
            sm.qty_change,
            sm.qty_after,
            sm.reference_type,
            sm.reference_id,
            sm.notes,
            sm.created_by,
            usr.username AS created_by_username,
            sm.created_at
        FROM stock_movements sm
        JOIN warehouses w ON w.id = sm.warehouse_id
        JOIN storage_locations sl ON sl.id = sm.location_id
        JOIN items i ON i.id = sm.item_id
        JOIN uoms u ON u.id = i.uom_id
        JOIN users usr ON usr.id = sm.created_by
        {where_sql}
        ORDER BY {order_by_sql}
        LIMIT %s OFFSET %s
        """,
        tuple([*params, limit, offset]),
    ).fetchall()
    return list(rows), total

