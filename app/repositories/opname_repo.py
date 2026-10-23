"""Repository SQL untuk Stock Opname dan pemeriksaan pembekuan lokasi (FR-07, PRD 6.6)."""

from typing import Any

from psycopg import Connection


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

