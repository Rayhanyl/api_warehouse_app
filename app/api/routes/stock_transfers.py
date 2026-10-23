"""Routes Stock Transfer dan aksi approve/ship/receive/cancel (FR-06, PRD 5.1, Lampiran B)."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from psycopg import Connection

from app.api.deps import get_client_ip, get_current_user
from app.core.database import get_conn
from app.core.exceptions import PermissionDenied
from app.core.permissions import (
    TRANSFER_APPROVE,
    TRANSFER_CREATE,
    TRANSFER_READ,
    TRANSFER_RECEIVE,
    TRANSFER_SHIP,
    require_permission,
)
from app.schemas.common import Page
from app.schemas.stock_transfer import (
    StockTransferCreate,
    StockTransferOut,
    StockTransferReceive,
    StockTransferSummaryOut,
    StockTransferUpdate,
)
from app.services import transfer_service

router = APIRouter(prefix="/stock-transfers", tags=["Stock Transfers"])


def _require_transfer_create_or_approve(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Dependency endpoint cancel Transfer: transfer:create (DRAFT) atau transfer:approve (APPROVED).

    Permission spesifik sesuai status dokumen diperiksa ulang di service setelah header dikunci.
    """
    perms: set[str] = set(current_user.get("permissions", []))
    if TRANSFER_CREATE not in perms and TRANSFER_APPROVE not in perms:
        raise PermissionDenied(
            f"Anda tidak memiliki izin '{TRANSFER_CREATE}' atau '{TRANSFER_APPROVE}' untuk membatalkan Transfer.",
            details={"required_permissions": [TRANSFER_CREATE, TRANSFER_APPROVE]},
        )
    return current_user


@router.get("", response_model=Page[StockTransferSummaryOut])
def list_stock_transfers(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    warehouse_id: int | None = Query(default=None),
    source_warehouse_id: int | None = Query(default=None),
    destination_warehouse_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    actor: dict[str, Any] = Depends(require_permission(TRANSFER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[StockTransferSummaryOut]:
    page = transfer_service.list_stock_transfers(
        conn,
        actor=actor,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        source_warehouse_id=source_warehouse_id,
        destination_warehouse_id=destination_warehouse_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[StockTransferSummaryOut](**page)


@router.post("", response_model=StockTransferOut, status_code=status.HTTP_201_CREATED)
def create_stock_transfer(
    payload: StockTransferCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(TRANSFER_CREATE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockTransferOut:
    created = transfer_service.create_stock_transfer(
        conn,
        actor=actor,
        source_warehouse_id=payload.source_warehouse_id,
        source_location_id=payload.source_location_id,
        destination_warehouse_id=payload.destination_warehouse_id,
        destination_location_id=payload.destination_location_id,
        notes=payload.notes,
        lines=[ln.model_dump() for ln in payload.lines],
        ip_address=get_client_ip(request),
    )
    return StockTransferOut(**created)


@router.get("/{transfer_id}", response_model=StockTransferOut)
def get_stock_transfer(
    transfer_id: int,
    actor: dict[str, Any] = Depends(require_permission(TRANSFER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockTransferOut:
    transfer = transfer_service.get_stock_transfer(
        conn, actor=actor, transfer_id=transfer_id
    )
    return StockTransferOut(**transfer)


@router.patch("/{transfer_id}", response_model=StockTransferOut)
def update_stock_transfer(
    transfer_id: int,
    payload: StockTransferUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(TRANSFER_CREATE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockTransferOut:
    updated = transfer_service.update_stock_transfer(
        conn,
        actor=actor,
        transfer_id=transfer_id,
        source_warehouse_id=payload.source_warehouse_id,
        source_location_id=payload.source_location_id,
        destination_warehouse_id=payload.destination_warehouse_id,
        destination_location_id=payload.destination_location_id,
        notes=payload.notes,
        lines=[ln.model_dump() for ln in payload.lines]
        if payload.lines is not None
        else None,
        ip_address=get_client_ip(request),
    )
    return StockTransferOut(**updated)


@router.post("/{transfer_id}/approve", response_model=StockTransferOut)
def approve_transfer(
    transfer_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(TRANSFER_APPROVE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockTransferOut:
    approved = transfer_service.approve_transfer(
        conn, actor=actor, transfer_id=transfer_id, ip_address=get_client_ip(request)
    )
    return StockTransferOut(**approved)


@router.post("/{transfer_id}/ship", response_model=StockTransferOut)
def ship_transfer(
    transfer_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(TRANSFER_SHIP)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockTransferOut:
    shipped = transfer_service.ship_transfer(
        conn, actor=actor, transfer_id=transfer_id, ip_address=get_client_ip(request)
    )
    return StockTransferOut(**shipped)


@router.post("/{transfer_id}/receive", response_model=StockTransferOut)
def receive_transfer(
    transfer_id: int,
    payload: StockTransferReceive,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(TRANSFER_RECEIVE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockTransferOut:
    received = transfer_service.receive_transfer(
        conn,
        actor=actor,
        transfer_id=transfer_id,
        lines=[ln.model_dump() for ln in payload.lines],
        ip_address=get_client_ip(request),
    )
    return StockTransferOut(**received)


@router.post("/{transfer_id}/cancel", response_model=StockTransferOut)
def cancel_transfer(
    transfer_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(_require_transfer_create_or_approve),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockTransferOut:
    cancelled = transfer_service.cancel_transfer(
        conn, actor=actor, transfer_id=transfer_id, ip_address=get_client_ip(request)
    )
    return StockTransferOut(**cancelled)

