"""Service pemeriksa penugasan gudang / Warehouse Scoping (PRD 3.2 & AC-12)."""

from typing import Any

from psycopg import Connection

from app.core.exceptions import WarehouseNotAssigned
from app.core.permissions import ROLE_SUPER_ADMIN, ROLE_WAREHOUSE_STAFF
from app.repositories import permission_repo


def ensure_warehouse_access(
    conn: Connection[dict[str, Any]],
    actor: dict[str, Any],
    warehouse_id: int,
) -> None:
    """Memastikan pengguna memiliki penugasan pada gudang terkait untuk aksi bertanda (g) di Matriks 3.1 PRD.

    - Super Admin selalu diizinkan pada seluruh gudang (PRD 3.0 & 3.2.6).
    - Peran lain yang mengeksekusi aksi bertanda (g) wajib memiliki baris pada user_warehouses.
      Bila tidak ditugaskan, melempar WarehouseNotAssigned (HTTP 403, kode WAREHOUSE_NOT_ASSIGNED).
    """
    if actor.get("role_name") == ROLE_SUPER_ADMIN:
        return

    assigned_ids = permission_repo.get_user_warehouse_ids(conn, int(actor["id"]))
    if int(warehouse_id) not in assigned_ids:
        raise WarehouseNotAssigned(
            "Anda tidak ditugaskan pada gudang yang terkait dengan transaksi/data ini.",
            details={
                "warehouse_id": int(warehouse_id),
                "assigned_warehouse_ids": assigned_ids,
            },
        )


def get_scoped_warehouse_ids_for_read(
    conn: Connection[dict[str, Any]],
    actor: dict[str, Any],
) -> list[int] | None:
    """Mengembalikan batasan daftar ID gudang untuk operasi baca (PRD 3.2 poin 5 & 6).

    - Warehouse Staff hanya boleh melihat dokumen & stok pada gudang yang ditugaskan -> mengembalikan list[int].
    - Super Admin, Warehouse Manager, Purchasing Staff, dan Auditor tidak dibatasi penugasan pada aksi baca -> None.
    """
    if actor.get("role_name") == ROLE_WAREHOUSE_STAFF:
        return permission_repo.get_user_warehouse_ids(conn, int(actor["id"]))
    return None

