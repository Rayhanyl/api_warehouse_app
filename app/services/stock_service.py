"""Service pembacaan saldo stok (per lokasi, per gudang, agregat lintas gudang) & buku besar (FR-03, FR-08, FR-11)."""

from datetime import datetime
from typing import Any

from psycopg import Connection

from app.core.exceptions import ValidationDomainError
from app.repositories import inventory_repo
from app.services import access_service
from app.utils.enums import MovementType, ReferenceType
from app.utils.pagination import build_order_by, normalize_pagination

STOCK_LOCATION_SORT_COLUMNS: dict[str, str] = {
    "warehouse_id": "cb.warehouse_id",
    "warehouse_code": "w.code",
    "location_id": "cb.location_id",
    "location_code": "sl.code",
    "item_id": "cb.item_id",
    "item_sku": "i.sku",
    "item_name": "i.name",
    "qty_on_hand": "cb.qty_on_hand",
    "qty_in_transit": "cb.qty_in_transit",
}

STOCK_WAREHOUSE_SORT_COLUMNS: dict[str, str] = {
    "warehouse_id": "cb.warehouse_id",
    "warehouse_code": "w.code",
    "item_id": "cb.item_id",
    "item_sku": "i.sku",
    "item_name": "i.name",
    "qty_on_hand": "cb.qty_on_hand",
    "qty_in_transit": "cb.qty_in_transit",
}

STOCK_SUMMARY_SORT_COLUMNS: dict[str, str] = {
    "item_id": "cb.item_id",
    "item_sku": "i.sku",
    "item_name": "i.name",
    "qty_on_hand": "cb.qty_on_hand",
    "qty_in_transit": "cb.qty_in_transit",
}

LEDGER_SORT_COLUMNS: dict[str, str] = {
    "id": "sm.id",
    "created_at": "sm.created_at",
    "movement_type": "sm.movement_type",
    "warehouse_id": "sm.warehouse_id",
    "item_id": "sm.item_id",
}

ALLOWED_MOVEMENT_TYPES: frozenset[str] = frozenset(m.value for m in MovementType)
ALLOWED_REFERENCE_TYPES: frozenset[str] = frozenset(r.value for r in ReferenceType)


def _resolve_read_scoping(
    conn: Connection[dict[str, Any]],
    actor: dict[str, Any],
    warehouse_id: int | None,
) -> list[int] | None:
    """Menerapkan aturan Warehouse Scoping pada pembacaan stok & ledger (PRD 3.2 poin 5 & 6).

    - Bila pengguna adalah Warehouse Staff dan meminta warehouse_id tertentu yang tidak ditugaskan -> 403 WAREHOUSE_NOT_ASSIGNED.
    - Bila Warehouse Staff tidak mengisi warehouse_id -> batasi hasil hanya pada gudang yang ditugaskan.
    - Peran lain (Super Admin, Warehouse Manager, Purchasing Staff, Auditor) -> tidak dibatasi penugasan pada aksi baca.
    """
    scoped_ids = access_service.get_scoped_warehouse_ids_for_read(conn, actor)
    if scoped_ids is not None and warehouse_id is not None:
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)
    return scoped_ids


def list_stock_by_location(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    warehouse_id: int | None = None,
    location_id: int | None = None,
    item_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=STOCK_LOCATION_SORT_COLUMNS,
        default_column="item_id",
        default_dir="ASC",
    )
    scoped_ids = _resolve_read_scoping(conn, actor, warehouse_id)

    items, total = inventory_repo.list_stock_by_location(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        scoped_warehouse_ids=scoped_ids,
        warehouse_id=warehouse_id,
        location_id=location_id,
        item_id=item_id,
        category_id=category_id,
        search=search,
        order_by_sql=order_by_sql,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def list_stock_by_warehouse(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    warehouse_id: int | None = None,
    item_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=STOCK_WAREHOUSE_SORT_COLUMNS,
        default_column="item_id",
        default_dir="ASC",
    )
    scoped_ids = _resolve_read_scoping(conn, actor, warehouse_id)

    items, total = inventory_repo.list_stock_by_warehouse(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        scoped_warehouse_ids=scoped_ids,
        warehouse_id=warehouse_id,
        item_id=item_id,
        category_id=category_id,
        search=search,
        order_by_sql=order_by_sql,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def list_stock_summary(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    warehouse_id: int | None = None,
    item_id: int | None = None,
    category_id: int | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=STOCK_SUMMARY_SORT_COLUMNS,
        default_column="item_id",
        default_dir="ASC",
    )
    scoped_ids = _resolve_read_scoping(conn, actor, warehouse_id)

    items, total = inventory_repo.list_stock_summary(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        scoped_warehouse_ids=scoped_ids,
        warehouse_id=warehouse_id,
        item_id=item_id,
        category_id=category_id,
        search=search,
        order_by_sql=order_by_sql,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def list_stock_movements(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    warehouse_id: int | None = None,
    location_id: int | None = None,
    item_id: int | None = None,
    movement_type: str | None = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=LEDGER_SORT_COLUMNS,
        default_column="id",
        default_dir="DESC",
    )

    clean_mov_type: str | None = None
    if movement_type is not None:
        clean_mov_type = movement_type.strip().upper()
        if clean_mov_type not in ALLOWED_MOVEMENT_TYPES:
            raise ValidationDomainError(
                f"Filter movement_type '{movement_type}' tidak valid.",
                details={
                    "movement_type": movement_type,
                    "allowed_values": sorted(ALLOWED_MOVEMENT_TYPES),
                },
            )

    clean_ref_type: str | None = None
    if reference_type is not None:
        clean_ref_type = reference_type.strip().upper()
        if clean_ref_type not in ALLOWED_REFERENCE_TYPES:
            raise ValidationDomainError(
                f"Filter reference_type '{reference_type}' tidak valid.",
                details={
                    "reference_type": reference_type,
                    "allowed_values": sorted(ALLOWED_REFERENCE_TYPES),
                },
            )

    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValidationDomainError(
            "Parameter date_from tidak boleh lebih besar dari date_to.",
            details={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            },
        )

    scoped_ids = _resolve_read_scoping(conn, actor, warehouse_id)

    items, total = inventory_repo.list_stock_movements(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        scoped_warehouse_ids=scoped_ids,
        warehouse_id=warehouse_id,
        location_id=location_id,
        item_id=item_id,
        movement_type=clean_mov_type,
        reference_type=clean_ref_type,
        reference_id=reference_id,
        date_from=date_from,
        date_to=date_to,
        order_by_sql=order_by_sql,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }

