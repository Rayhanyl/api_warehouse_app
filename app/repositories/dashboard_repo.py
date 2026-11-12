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

    # Total macam SKU aktif
    row_active = conn.execute(
        "SELECT COUNT(*)::INT AS total FROM items WHERE is_active = TRUE"
    ).fetchone()
    total_active_items = int(row_active["total"]) if row_active else 0

    # Total kuantitas on-hand
    if warehouse_ids is None:
        row_on_hand = conn.execute(
            "SELECT COALESCE(SUM(qty_on_hand), 0)::NUMERIC(18, 4) AS total FROM inventory_balances"
        ).fetchone()
    else:
        row_on_hand = conn.execute(
            """
            SELECT COALESCE(SUM(qty_on_hand), 0)::NUMERIC(18, 4) AS total
            FROM inventory_balances
            WHERE warehouse_id = ANY(%s)
            """,
            (warehouse_ids,),
        ).fetchone()
    total_qty_on_hand = (
        Decimal(str(row_on_hand["total"])) if row_on_hand else Decimal("0.0000")
    )

    # Total kuantitas in-transit
    if warehouse_ids is None:
        row_transit = conn.execute(
            """
            SELECT COALESCE(SUM(stl.qty), 0)::NUMERIC(18, 4) AS total
            FROM stock_transfers st
            JOIN stock_transfer_lines stl ON stl.transfer_id = st.id
            WHERE st.status = 'SHIPPED'
            """
        ).fetchone()
    else:
        row_transit = conn.execute(
            """
            SELECT COALESCE(SUM(stl.qty), 0)::NUMERIC(18, 4) AS total
            FROM stock_transfers st
            JOIN stock_transfer_lines stl ON stl.transfer_id = st.id
            WHERE st.status = 'SHIPPED' AND st.destination_warehouse_id = ANY(%s)
            """,
            (warehouse_ids,),
        ).fetchone()
    total_qty_in_transit = (
        Decimal(str(row_transit["total"])) if row_transit else Decimal("0.0000")
    )

    # Low stock items count (SKU aktif dengan saldo di gudang <= 0)
    if warehouse_ids is None:
        row_low = conn.execute(
            """
            WITH item_stock AS (
                SELECT
                    i.id,
                    COALESCE(SUM(ib.qty_on_hand), 0) AS on_hand
                FROM items i
                LEFT JOIN inventory_balances ib ON i.id = ib.item_id
                WHERE i.is_active = TRUE
                GROUP BY i.id
            )
            SELECT COUNT(*)::INT AS total FROM item_stock WHERE on_hand <= 0
            """
        ).fetchone()
    else:
        row_low = conn.execute(
            """
            WITH item_stock AS (
                SELECT
                    i.id,
                    COALESCE(SUM(ib.qty_on_hand), 0) AS on_hand
                FROM items i
                LEFT JOIN inventory_balances ib ON i.id = ib.item_id AND ib.warehouse_id = ANY(%s)
                WHERE i.is_active = TRUE
                GROUP BY i.id
            )
            SELECT COUNT(*)::INT AS total FROM item_stock WHERE on_hand <= 0
            """,
            (warehouse_ids,),
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

    # PO menunggu GR (ISSUED / PARTIALLY_RECEIVED)
    if warehouse_ids is None:
        po_row = conn.execute(
            "SELECT COUNT(*)::INT AS total FROM purchase_orders WHERE status IN ('ISSUED', 'PARTIALLY_RECEIVED')"
        ).fetchone()
    else:
        po_row = conn.execute(
            """
            SELECT COUNT(*)::INT AS total
            FROM purchase_orders
            WHERE status IN ('ISSUED', 'PARTIALLY_RECEIVED') AND warehouse_id = ANY(%s)
            """,
            (warehouse_ids,),
        ).fetchone()
    pending_po_receipt_count = int(po_row["total"]) if po_row else 0

    # GR DRAFT belum diposting
    if warehouse_ids is None:
        gr_row = conn.execute(
            "SELECT COUNT(*)::INT AS total FROM goods_receipts WHERE status = 'DRAFT'"
        ).fetchone()
    else:
        gr_row = conn.execute(
            "SELECT COUNT(*)::INT AS total FROM goods_receipts WHERE status = 'DRAFT' AND warehouse_id = ANY(%s)",
            (warehouse_ids,),
        ).fetchone()
    draft_gr_count = int(gr_row["total"]) if gr_row else 0

    # Transfer APPROVED menunggu dikirim (berdasarkan source_warehouse_id)
    if warehouse_ids is None:
        trf_ship_row = conn.execute(
            "SELECT COUNT(*)::INT AS total FROM stock_transfers WHERE status = 'APPROVED'"
        ).fetchone()
    else:
        trf_ship_row = conn.execute(
            """
            SELECT COUNT(*)::INT AS total
            FROM stock_transfers
            WHERE status = 'APPROVED' AND source_warehouse_id = ANY(%s)
            """,
            (warehouse_ids,),
        ).fetchone()
    pending_transfer_ship_count = int(trf_ship_row["total"]) if trf_ship_row else 0

    # Transfer SHIPPED menunggu diterima (berdasarkan destination_warehouse_id)
    if warehouse_ids is None:
        trf_recv_row = conn.execute(
            "SELECT COUNT(*)::INT AS total FROM stock_transfers WHERE status = 'SHIPPED'"
        ).fetchone()
    else:
        trf_recv_row = conn.execute(
            """
            SELECT COUNT(*)::INT AS total
            FROM stock_transfers
            WHERE status = 'SHIPPED' AND destination_warehouse_id = ANY(%s)
            """,
            (warehouse_ids,),
        ).fetchone()
    pending_transfer_receive_count = (
        int(trf_recv_row["total"]) if trf_recv_row else 0
    )

    # Opname aktif (IN_PROGRESS / WAITING_APPROVAL)
    if warehouse_ids is None:
        opn_row = conn.execute(
            "SELECT COUNT(*)::INT AS total FROM stock_opnames WHERE status IN ('IN_PROGRESS', 'WAITING_APPROVAL')"
        ).fetchone()
    else:
        opn_row = conn.execute(
            """
            SELECT COUNT(*)::INT AS total
            FROM stock_opnames
            WHERE status IN ('IN_PROGRESS', 'WAITING_APPROVAL') AND warehouse_id = ANY(%s)
            """,
            (warehouse_ids,),
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
