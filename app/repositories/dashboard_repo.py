"""Repository SQL untuk agregasi data dashboard operasional (DSH-F01, AC-38)."""

from decimal import Decimal
from typing import Any

from psycopg import Connection


def get_stock_summary(
    conn: Connection[dict[str, Any]], warehouse_ids: list[int] | None
) -> dict[str, Any]:
    """Mengambil ringkasan metrik stok (total SKU, total on-hand, total in-transit, dan low stock)."""
    if warehouse_ids is not None and len(warehouse_ids) == 0:
        return {
            "total_active_items": 0,
            "total_qty_on_hand": Decimal("0.0000"),
            "total_qty_in_transit": Decimal("0.0000"),
            "low_stock_items_count": 0,
        }

    # Total macam SKU aktif (global atau yang dikelola pada warehouse_ids terkait yang aktif)
    if warehouse_ids is None:
        row_active = conn.execute(
            "SELECT COUNT(*)::INT AS total FROM items WHERE is_active = TRUE"
        ).fetchone()
    else:
        row_active = conn.execute(
            """
            SELECT COUNT(DISTINCT i.id)::INT AS total
            FROM items i
            WHERE i.is_active = TRUE
              AND (
                  EXISTS (
                      SELECT 1
                      FROM inventory_balances ib
                      JOIN warehouses w ON w.id = ib.warehouse_id
                      WHERE ib.item_id = i.id
                        AND w.is_active = TRUE
                        AND ib.warehouse_id = ANY(%s)
                  )
                  OR EXISTS (
                      SELECT 1
                      FROM stock_transfer_lines stl
                      JOIN stock_transfers st ON st.id = stl.transfer_id
                      JOIN warehouses w ON w.id = st.destination_warehouse_id
                      WHERE stl.item_id = i.id
                        AND st.status = 'SHIPPED'
                        AND w.is_active = TRUE
                        AND st.destination_warehouse_id = ANY(%s)
                  )
              )
            """,
            (warehouse_ids, warehouse_ids),
        ).fetchone()
    total_active_items = int(row_active["total"]) if row_active else 0

    wh_params: tuple[Any, ...] = (warehouse_ids,) if warehouse_ids is not None else ()

    # Total kuantitas on-hand (barang aktif pada gudang aktif)
    on_hand_wh_filter = " AND ib.warehouse_id = ANY(%s)" if warehouse_ids is not None else ""
    row_on_hand = conn.execute(
        f"""
        SELECT COALESCE(SUM(ib.qty_on_hand), 0)::NUMERIC(18, 4) AS total
        FROM inventory_balances ib
        JOIN items i ON i.id = ib.item_id
        JOIN warehouses w ON w.id = ib.warehouse_id
        WHERE i.is_active = TRUE
          AND w.is_active = TRUE{on_hand_wh_filter}
        """,
        wh_params,
    ).fetchone()
    total_qty_on_hand = (
        Decimal(str(row_on_hand["total"])) if row_on_hand else Decimal("0.0000")
    )

    # Total kuantitas in-transit (menuju gudang aktif dalam cakupan)
    transit_wh_filter = (
        " AND st.destination_warehouse_id = ANY(%s)" if warehouse_ids is not None else ""
    )
    row_transit = conn.execute(
        f"""
        SELECT COALESCE(SUM(stl.qty), 0)::NUMERIC(18, 4) AS total
        FROM stock_transfers st
        JOIN stock_transfer_lines stl ON stl.transfer_id = st.id
        JOIN items i ON i.id = stl.item_id
        JOIN warehouses w ON w.id = st.destination_warehouse_id
        WHERE st.status = 'SHIPPED'
          AND i.is_active = TRUE
          AND w.is_active = TRUE{transit_wh_filter}
        """,
        wh_params,
    ).fetchone()
    total_qty_in_transit = (
        Decimal(str(row_transit["total"])) if row_transit else Decimal("0.0000")
    )

    # Low stock items count: selaras 1:1 dengan /stock/by-warehouse?critical_only=true
    # (evaluasi per pasangan (warehouse_id, item_id) untuk gudang & barang aktif dengan min_stock > 0)
    low_wh_filter = " AND cb.warehouse_id = ANY(%s)" if warehouse_ids is not None else ""
    row_low = conn.execute(
        f"""
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
                COALESCE(wb.qty_on_hand, 0.0000)::NUMERIC(18, 4) AS qty_on_hand
            FROM wh_balance wb
            FULL OUTER JOIN in_transit_wh it
                ON wb.warehouse_id = it.warehouse_id
               AND wb.item_id = it.item_id
        )
        SELECT COUNT(*)::INT AS total
        FROM cb
        JOIN warehouses w ON w.id = cb.warehouse_id
        JOIN items i ON i.id = cb.item_id
        WHERE w.is_active = TRUE
          AND i.is_active = TRUE
          AND i.min_stock > 0
          AND cb.qty_on_hand <= i.min_stock{low_wh_filter}
        """,
        wh_params,
    ).fetchone()
    low_stock_items_count = int(row_low["total"]) if row_low else 0

    return {
        "total_active_items": total_active_items,
        "total_qty_on_hand": total_qty_on_hand,
        "total_qty_in_transit": total_qty_in_transit,
        "low_stock_items_count": low_stock_items_count,
    }


def get_pending_actions(
    conn: Connection[dict[str, Any]], warehouse_ids: list[int] | None
) -> dict[str, int]:
    """Mengambil jumlah dokumen tertunda yang memerlukan tindakan operasional."""
    if warehouse_ids is not None and len(warehouse_ids) == 0:
        return {
            "pending_po_receipt_count": 0,
            "draft_gr_count": 0,
            "pending_transfer_ship_count": 0,
            "pending_transfer_receive_count": 0,
            "active_opname_count": 0,
        }

    wh_params: tuple[Any, ...] = (warehouse_ids,) if warehouse_ids is not None else ()

    # PO menunggu GR (ISSUED / PARTIALLY_RECEIVED) pada gudang aktif
    po_wh_filter = " AND po.warehouse_id = ANY(%s)" if warehouse_ids is not None else ""
    po_row = conn.execute(
        f"""
        SELECT COUNT(*)::INT AS total
        FROM purchase_orders po
        JOIN warehouses w ON w.id = po.warehouse_id
        WHERE po.status IN ('ISSUED', 'PARTIALLY_RECEIVED')
          AND w.is_active = TRUE{po_wh_filter}
        """,
        wh_params,
    ).fetchone()
    pending_po_receipt_count = int(po_row["total"]) if po_row else 0

    # GR DRAFT belum diposting pada gudang aktif
    gr_wh_filter = " AND gr.warehouse_id = ANY(%s)" if warehouse_ids is not None else ""
    gr_row = conn.execute(
        f"""
        SELECT COUNT(*)::INT AS total
        FROM goods_receipts gr
        JOIN warehouses w ON w.id = gr.warehouse_id
        WHERE gr.status = 'DRAFT'
          AND w.is_active = TRUE{gr_wh_filter}
        """,
        wh_params,
    ).fetchone()
    draft_gr_count = int(gr_row["total"]) if gr_row else 0

    # Transfer APPROVED menunggu dikirim (berdasarkan source_warehouse_id aktif)
    trf_ship_filter = (
        " AND st.source_warehouse_id = ANY(%s)" if warehouse_ids is not None else ""
    )
    trf_ship_row = conn.execute(
        f"""
        SELECT COUNT(*)::INT AS total
        FROM stock_transfers st
        JOIN warehouses w ON w.id = st.source_warehouse_id
        WHERE st.status = 'APPROVED'
          AND w.is_active = TRUE{trf_ship_filter}
        """,
        wh_params,
    ).fetchone()
    pending_transfer_ship_count = int(trf_ship_row["total"]) if trf_ship_row else 0

    # Transfer SHIPPED menunggu diterima (berdasarkan destination_warehouse_id aktif)
    trf_recv_filter = (
        " AND st.destination_warehouse_id = ANY(%s)" if warehouse_ids is not None else ""
    )
    trf_recv_row = conn.execute(
        f"""
        SELECT COUNT(*)::INT AS total
        FROM stock_transfers st
        JOIN warehouses w ON w.id = st.destination_warehouse_id
        WHERE st.status = 'SHIPPED'
          AND w.is_active = TRUE{trf_recv_filter}
        """,
        wh_params,
    ).fetchone()
    pending_transfer_receive_count = (
        int(trf_recv_row["total"]) if trf_recv_row else 0
    )

    # Opname aktif (IN_PROGRESS / WAITING_L1_APPROVAL / WAITING_L2_APPROVAL) pada gudang aktif
    opn_wh_filter = " AND so.warehouse_id = ANY(%s)" if warehouse_ids is not None else ""
    opn_row = conn.execute(
        f"""
        SELECT COUNT(*)::INT AS total
        FROM stock_opnames so
        JOIN warehouses w ON w.id = so.warehouse_id
        WHERE so.status IN ('IN_PROGRESS', 'WAITING_L1_APPROVAL', 'WAITING_L2_APPROVAL', 'WAITING_APPROVAL')
          AND w.is_active = TRUE{opn_wh_filter}
        """,
        wh_params,
    ).fetchone()
    active_opname_count = int(opn_row["total"]) if opn_row else 0

    return {
        "pending_po_receipt_count": pending_po_receipt_count,
        "draft_gr_count": draft_gr_count,
        "pending_transfer_ship_count": pending_transfer_ship_count,
        "pending_transfer_receive_count": pending_transfer_receive_count,
        "active_opname_count": active_opname_count,
    }


def get_recent_activities(
    conn: Connection[dict[str, Any]],
    warehouse_ids: list[int] | None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Mengambil 5–8 mutasi stok terakhir beserta nomor referensi dokumen dan aktor."""
    if warehouse_ids is not None and len(warehouse_ids) == 0:
        return []

    sql = """
        SELECT
            sm.id,
            sm.created_at,
            sm.movement_type,
            sm.reference_type,
            sm.reference_id,
            CASE
                WHEN sm.reference_type = 'GOODS_RECEIPT' THEN gr.gr_number
                WHEN sm.reference_type = 'STOCK_TRANSFER' THEN st.transfer_number
                WHEN sm.reference_type = 'STOCK_OPNAME' THEN so.opname_number
                ELSE NULL
            END AS reference_number,
            sm.warehouse_id,
            w.code AS warehouse_code,
            w.name AS warehouse_name,
            sm.item_id,
            i.sku AS item_sku,
            i.name AS item_name,
            sm.qty_change,
            sm.qty_after,
            COALESCE(u.full_name, u.username) AS actor_name
        FROM stock_movements sm
        JOIN items i ON sm.item_id = i.id
        JOIN warehouses w ON sm.warehouse_id = w.id
        LEFT JOIN users u ON sm.created_by = u.id
        LEFT JOIN goods_receipts gr ON sm.reference_type = 'GOODS_RECEIPT' AND sm.reference_id = gr.id
        LEFT JOIN stock_transfers st ON sm.reference_type = 'STOCK_TRANSFER' AND sm.reference_id = st.id
        LEFT JOIN stock_opnames so ON sm.reference_type = 'STOCK_OPNAME' AND sm.reference_id = so.id
    """
    params: list[Any] = []
    if warehouse_ids is not None:
        sql += " WHERE sm.warehouse_id = ANY(%s)"
        params.append(warehouse_ids)

    sql += " ORDER BY sm.created_at DESC, sm.id DESC LIMIT %s"
    params.append(limit)

    rows = conn.execute(sql, tuple(params)).fetchall()
    return list(rows)


def get_assigned_warehouses(
    conn: Connection[dict[str, Any]], warehouse_ids: list[int] | None
) -> list[dict[str, Any]]:
    """Mengambil daftar gudang aktif yang menjadi cakupan penilaian data."""
    if warehouse_ids is not None and len(warehouse_ids) == 0:
        return []

    if warehouse_ids is None:
        rows = conn.execute(
            "SELECT id, code, name FROM warehouses WHERE is_active = TRUE ORDER BY code"
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, code, name
            FROM warehouses
            WHERE id = ANY(%s) AND is_active = TRUE
            ORDER BY code
            """,
            (warehouse_ids,),
        ).fetchall()
    return list(rows)
