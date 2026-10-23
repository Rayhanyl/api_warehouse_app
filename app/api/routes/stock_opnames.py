"""Routes Stock Opname dan aksi start/count/submit/approve/reject/cancel (FR-07, PRD 5.1, Lampiran B)."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from psycopg import Connection

from app.api.deps import get_client_ip
from app.core.database import get_conn
from app.core.permissions import (
    OPNAME_APPROVE,
    OPNAME_COUNT,
    OPNAME_MANAGE,
    OPNAME_READ,
    require_permission,
)
from app.schemas.common import Page
from app.schemas.stock_opname import (
    StockOpnameCountRequest,
    StockOpnameCreate,
    StockOpnameOut,
    StockOpnameRejectRequest,
    StockOpnameSummaryOut,
    StockOpnameUpdate,
)
from app.services import opname_service

router = APIRouter(prefix="/stock-opnames", tags=["Stock Opnames"])


@router.get("", response_model=Page[StockOpnameSummaryOut])
def list_stock_opnames(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    warehouse_id: int | None = Query(default=None),
    location_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    actor: dict[str, Any] = Depends(require_permission(OPNAME_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[StockOpnameSummaryOut]:
    page = opname_service.list_stock_opnames(
        conn,
        actor=actor,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        location_id=location_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[StockOpnameSummaryOut](**page)


@router.post("", response_model=StockOpnameOut, status_code=status.HTTP_201_CREATED)
def create_stock_opname(
    payload: StockOpnameCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(OPNAME_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockOpnameOut:
    created = opname_service.create_stock_opname(
        conn,
        actor=actor,
        warehouse_id=payload.warehouse_id,
        location_id=payload.location_id,
        notes=payload.notes,
        ip_address=get_client_ip(request),
    )
    return StockOpnameOut(**created)


@router.get("/{opname_id}", response_model=StockOpnameOut)
def get_stock_opname(
    opname_id: int,
    actor: dict[str, Any] = Depends(require_permission(OPNAME_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockOpnameOut:
    opname = opname_service.get_stock_opname(
        conn, actor=actor, opname_id=opname_id
    )
    return StockOpnameOut(**opname)


@router.patch("/{opname_id}", response_model=StockOpnameOut)
def update_stock_opname(
    opname_id: int,
    payload: StockOpnameUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(OPNAME_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockOpnameOut:
    updated = opname_service.update_stock_opname(
        conn,
        actor=actor,
        opname_id=opname_id,
        location_id=payload.location_id,
        clear_location=payload.clear_location,
        notes=payload.notes,
        ip_address=get_client_ip(request),
    )
    return StockOpnameOut(**updated)


@router.post("/{opname_id}/start", response_model=StockOpnameOut)
def start_stock_opname(
    opname_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(OPNAME_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockOpnameOut:
    started = opname_service.start_stock_opname(
        conn,
        actor=actor,
        opname_id=opname_id,
        ip_address=get_client_ip(request),
    )
    return StockOpnameOut(**started)


@router.post("/{opname_id}/count", response_model=StockOpnameOut)
@router.post("/{opname_id}/lines", response_model=StockOpnameOut)
@router.put("/{opname_id}/lines", response_model=StockOpnameOut)
def record_opname_counts(
    opname_id: int,
    payload: StockOpnameCountRequest,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(OPNAME_COUNT)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockOpnameOut:
    counted = opname_service.record_opname_counts(
        conn,
        actor=actor,
        opname_id=opname_id,
        lines=[ln.model_dump() for ln in payload.lines],
        ip_address=get_client_ip(request),
    )
    return StockOpnameOut(**counted)


@router.post("/{opname_id}/submit", response_model=StockOpnameOut)
def submit_stock_opname(
    opname_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(OPNAME_COUNT)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockOpnameOut:
    submitted = opname_service.submit_stock_opname(
        conn,
        actor=actor,
        opname_id=opname_id,
        ip_address=get_client_ip(request),
    )
    return StockOpnameOut(**submitted)


@router.post("/{opname_id}/approve", response_model=StockOpnameOut)
def approve_stock_opname(
    opname_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(OPNAME_APPROVE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockOpnameOut:
    approved = opname_service.approve_stock_opname(
        conn,
        actor=actor,
        opname_id=opname_id,
        ip_address=get_client_ip(request),
    )
    return StockOpnameOut(**approved)


@router.post("/{opname_id}/reject", response_model=StockOpnameOut)
def reject_stock_opname(
    opname_id: int,
    payload: StockOpnameRejectRequest,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(OPNAME_APPROVE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockOpnameOut:
    rejected = opname_service.reject_stock_opname(
        conn,
        actor=actor,
        opname_id=opname_id,
        rejection_reason=payload.rejection_reason,
        ip_address=get_client_ip(request),
    )
    return StockOpnameOut(**rejected)


@router.post("/{opname_id}/cancel", response_model=StockOpnameOut)
def cancel_stock_opname(
    opname_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(OPNAME_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StockOpnameOut:
    cancelled = opname_service.cancel_stock_opname(
        conn,
        actor=actor,
        opname_id=opname_id,
        ip_address=get_client_ip(request),
    )
    return StockOpnameOut(**cancelled)

