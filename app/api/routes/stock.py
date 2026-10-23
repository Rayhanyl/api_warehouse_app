"""Routes Pembacaan Saldo Stok (per lokasi, per gudang, agregat) dan Buku Besar Pergerakan Stok (FR-03, FR-08, Matriks 3.1)."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.core.database import get_conn
from app.core.permissions import LEDGER_READ, STOCK_READ, require_permission
from app.schemas.common import Page
from app.schemas.stock import (
    StockLocationBalanceOut,
    StockMovementOut,
    StockSummaryOut,
    StockWarehouseBalanceOut,
)
from app.services import stock_service

router = APIRouter(prefix="/stock", tags=["Stock & Ledger"])


@router.get("/balances", response_model=Page[StockLocationBalanceOut])
@router.get("/by-location", response_model=Page[StockLocationBalanceOut])
def list_stock_by_location(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    warehouse_id: int | None = Query(default=None),
    location_id: int | None = Query(default=None),
    item_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    actor: dict[str, Any] = Depends(require_permission(STOCK_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[StockLocationBalanceOut]:
    page = stock_service.list_stock_by_location(
        conn,
        actor=actor,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        location_id=location_id,
        item_id=item_id,
        category_id=category_id,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[StockLocationBalanceOut](**page)


@router.get("/by-warehouse", response_model=Page[StockWarehouseBalanceOut])
def list_stock_by_warehouse(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    warehouse_id: int | None = Query(default=None),
    item_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    actor: dict[str, Any] = Depends(require_permission(STOCK_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[StockWarehouseBalanceOut]:
    page = stock_service.list_stock_by_warehouse(
        conn,
        actor=actor,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        item_id=item_id,
        category_id=category_id,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[StockWarehouseBalanceOut](**page)


@router.get("/summary", response_model=Page[StockSummaryOut])
def list_stock_summary(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    warehouse_id: int | None = Query(default=None),
    item_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    actor: dict[str, Any] = Depends(require_permission(STOCK_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[StockSummaryOut]:
    page = stock_service.list_stock_summary(
        conn,
        actor=actor,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        item_id=item_id,
        category_id=category_id,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[StockSummaryOut](**page)


@router.get("/movements", response_model=Page[StockMovementOut])
@router.get("/ledger", response_model=Page[StockMovementOut])
def list_stock_movements(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    warehouse_id: int | None = Query(default=None),
    location_id: int | None = Query(default=None),
    item_id: int | None = Query(default=None),
    movement_type: str | None = Query(default=None),
    reference_type: str | None = Query(default=None),
    reference_id: int | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    actor: dict[str, Any] = Depends(require_permission(LEDGER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[StockMovementOut]:
    page = stock_service.list_stock_movements(
        conn,
        actor=actor,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        location_id=location_id,
        item_id=item_id,
        movement_type=movement_type,
        reference_type=reference_type,
        reference_id=reference_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[StockMovementOut](**page)

