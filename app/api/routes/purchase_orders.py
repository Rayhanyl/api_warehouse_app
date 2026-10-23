"""Routes Purchase Order (PO) dan transisi statusnya (FR-04, PRD 5.1, Lampiran B)."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from psycopg import Connection

from app.api.deps import get_client_ip, get_current_user
from app.core.database import get_conn
from app.core.exceptions import PermissionDenied
from app.core.permissions import (
    PO_CANCEL,
    PO_CLOSE,
    PO_CREATE,
    PO_ISSUE,
    PO_READ,
    require_permission,
)
from app.schemas.common import Page
from app.schemas.purchase_order import (
    PurchaseOrderCloseRequest,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    PurchaseOrderSummaryOut,
    PurchaseOrderUpdate,
)
from app.services import po_service

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


def _require_po_cancel_or_create(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Dependency route untuk endpoint cancel PO (menerima po:create untuk DRAFT atau po:cancel untuk ISSUED)."""
    perms: set[str] = set(current_user.get("permissions", []))
    if PO_CREATE not in perms and PO_CANCEL not in perms:
        raise PermissionDenied(
            f"Anda tidak memiliki izin '{PO_CANCEL}' atau '{PO_CREATE}' untuk membatalkan Purchase Order.",
            details={"required_permissions": [PO_CREATE, PO_CANCEL]},
        )
    return current_user


@router.get("", response_model=Page[PurchaseOrderSummaryOut])
def list_purchase_orders(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    warehouse_id: int | None = Query(default=None),
    supplier_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    actor: dict[str, Any] = Depends(require_permission(PO_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[PurchaseOrderSummaryOut]:
    page = po_service.list_purchase_orders(
        conn,
        actor=actor,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        supplier_id=supplier_id,
        status=status_filter,
        date_from=date_from,
        date_to=date_to,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[PurchaseOrderSummaryOut](**page)


@router.post(
    "",
    response_model=PurchaseOrderOut,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(PO_CREATE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    created = po_service.create_purchase_order(
        conn,
        actor=actor,
        supplier_id=payload.supplier_id,
        warehouse_id=payload.warehouse_id,
        order_date=payload.order_date,
        notes=payload.notes,
        lines=[ln.model_dump() for ln in payload.lines],
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**created)


@router.get("/{po_id}", response_model=PurchaseOrderOut)
def get_purchase_order(
    po_id: int,
    actor: dict[str, Any] = Depends(require_permission(PO_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    po = po_service.get_purchase_order(conn, actor=actor, po_id=po_id)
    return PurchaseOrderOut(**po)


@router.patch("/{po_id}", response_model=PurchaseOrderOut)
def update_purchase_order(
    po_id: int,
    payload: PurchaseOrderUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(PO_CREATE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    updated = po_service.update_purchase_order(
        conn,
        actor=actor,
        po_id=po_id,
        supplier_id=payload.supplier_id,
        warehouse_id=payload.warehouse_id,
        order_date=payload.order_date,
        notes=payload.notes,
        lines=[ln.model_dump() for ln in payload.lines]
        if payload.lines is not None
        else None,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**updated)


@router.post("/{po_id}/issue", response_model=PurchaseOrderOut)
def issue_purchase_order(
    po_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(PO_ISSUE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    updated = po_service.issue_purchase_order(
        conn,
        actor=actor,
        po_id=po_id,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**updated)


@router.post("/{po_id}/cancel", response_model=PurchaseOrderOut)
def cancel_purchase_order(
    po_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(_require_po_cancel_or_create),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    updated = po_service.cancel_purchase_order(
        conn,
        actor=actor,
        po_id=po_id,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**updated)


@router.post("/{po_id}/close", response_model=PurchaseOrderOut)
def close_purchase_order(
    po_id: int,
    payload: PurchaseOrderCloseRequest,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(PO_CLOSE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    updated = po_service.close_purchase_order(
        conn,
        actor=actor,
        po_id=po_id,
        closed_reason=payload.closed_reason,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**updated)

