"""Routes Goods Receipt (GR) dan aksi posting/pembatalannya (FR-05, PRD 5.1, Lampiran B)."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from psycopg import Connection

from app.api.deps import get_client_ip
from app.core.database import get_conn
from app.core.permissions import GR_MANAGE, GR_READ, require_permission
from app.schemas.common import Page
from app.schemas.goods_receipt import (
    GoodsReceiptCreate,
    GoodsReceiptOut,
    GoodsReceiptSummaryOut,
    GoodsReceiptUpdate,
)
from app.services import gr_service

router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])


@router.get("", response_model=Page[GoodsReceiptSummaryOut])
def list_goods_receipts(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    warehouse_id: int | None = Query(default=None),
    po_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    actor: dict[str, Any] = Depends(require_permission(GR_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[GoodsReceiptSummaryOut]:
    page = gr_service.list_goods_receipts(
        conn,
        actor=actor,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        po_id=po_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[GoodsReceiptSummaryOut](**page)


@router.post(
    "",
    response_model=GoodsReceiptOut,
    status_code=status.HTTP_201_CREATED,
)
def create_goods_receipt(
    payload: GoodsReceiptCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(GR_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> GoodsReceiptOut:
    created = gr_service.create_goods_receipt(
        conn,
        actor=actor,
        po_id=payload.po_id,
        received_date=payload.received_date,
        notes=payload.notes,
        lines=[ln.model_dump() for ln in payload.lines],
        ip_address=get_client_ip(request),
    )
    return GoodsReceiptOut(**created)


@router.get("/{gr_id}", response_model=GoodsReceiptOut)
def get_goods_receipt(
    gr_id: int,
    actor: dict[str, Any] = Depends(require_permission(GR_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> GoodsReceiptOut:
    gr = gr_service.get_goods_receipt(conn, actor=actor, gr_id=gr_id)
    return GoodsReceiptOut(**gr)


@router.patch("/{gr_id}", response_model=GoodsReceiptOut)
def update_goods_receipt(
    gr_id: int,
    payload: GoodsReceiptUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(GR_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> GoodsReceiptOut:
    updated = gr_service.update_goods_receipt(
        conn,
        actor=actor,
        gr_id=gr_id,
        received_date=payload.received_date,
        notes=payload.notes,
        lines=[ln.model_dump() for ln in payload.lines]
        if payload.lines is not None
        else None,
        ip_address=get_client_ip(request),
    )
    return GoodsReceiptOut(**updated)


@router.post("/{gr_id}/post", response_model=GoodsReceiptOut)
def post_goods_receipt(
    gr_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(GR_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> GoodsReceiptOut:
    posted = gr_service.post_goods_receipt(
        conn,
        actor=actor,
        gr_id=gr_id,
        ip_address=get_client_ip(request),
    )
    return GoodsReceiptOut(**posted)


@router.post("/{gr_id}/cancel", response_model=GoodsReceiptOut)
def cancel_goods_receipt(
    gr_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(GR_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> GoodsReceiptOut:
    cancelled = gr_service.cancel_goods_receipt(
        conn,
        actor=actor,
        gr_id=gr_id,
        ip_address=get_client_ip(request),
    )
    return GoodsReceiptOut(**cancelled)

