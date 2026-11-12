"""Service agregasi data dashboard operasional (DSH-F01, AC-38)."""

from typing import Any

from psycopg import Connection

from app.repositories import dashboard_repo
from app.services import access_service


def get_dashboard_summary(
    conn: Connection[dict[str, Any]], actor: dict[str, Any]
) -> dict[str, Any]:
    """Menghasilkan ringkasan data dashboard terisolasi per penugasan gudang aktor (BR-GLB-007, AC-38).

    - Super Admin dan Auditor membaca seluruh gudang aktif (unscoped: None).
    - Peran operasional (Warehouse Manager, Purchasing Staff, Warehouse Staff) dibatasi pada user_warehouses.
    - Jika pengguna tidak memiliki penugasan gudang, metrik mengembalikan nilai 0 dan list kosong secara aman.
    """
    scoped_wh_ids = access_service.get_scoped_warehouse_ids_for_read(conn, actor)

    stock_summary = dashboard_repo.get_stock_summary(conn, scoped_wh_ids)
    pending_actions = dashboard_repo.get_pending_actions(conn, scoped_wh_ids)
    recent_activities = dashboard_repo.get_recent_activities(
        conn, scoped_wh_ids, limit=8
    )
    assigned_warehouses = dashboard_repo.get_assigned_warehouses(
        conn, scoped_wh_ids
    )

    return {
        "stock_summary": stock_summary,
        "pending_actions": pending_actions,
        "recent_activities": recent_activities,
        "assigned_warehouses": assigned_warehouses,
    }
