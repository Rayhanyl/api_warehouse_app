"""Routes Purchase Order (PO) dan transisi statusnya (FR-04, PRD 5.1, Lampiran B)."""

from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request, status
from psycopg import Connection

from app.api.deps import get_client_ip, get_current_user
from app.core.database import get_conn
from app.core.exceptions import PermissionDenied
from app.core.permissions import (
    PO_APPROVE_L1,
    PO_APPROVE_L2,
    PO_CANCEL,
    PO_CLOSE,
    PO_CREATE,
    PO_ISSUE,
    PO_READ,
    require_any_permission,
    require_permission,
)
from app.schemas.common import OptDateQuery, OptIntQuery, OptStrQuery, Page
from app.schemas.purchase_order import (
    PurchaseOrderApproveRequest,
    PurchaseOrderCloseRequest,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    PurchaseOrderRejectRequest,
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
    warehouse_id: OptIntQuery = Query(default=None),
    supplier_id: OptIntQuery = Query(default=None),
    status_filter: OptStrQuery = Query(default=None, alias="status"),
    date_from: OptDateQuery = Query(default=None),
    date_to: OptDateQuery = Query(default=None),
    overdue_only: bool = Query(default=False),
    search: OptStrQuery = Query(default=None),
    sort_by: OptStrQuery = Query(default=None),
    sort_dir: OptStrQuery = Query(default=None),
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
        overdue_only=overdue_only,
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
        expected_delivery_date=payload.expected_delivery_date,
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
        expected_delivery_date=payload.expected_delivery_date,
        expected_delivery_date_provided="expected_delivery_date" in payload.model_fields_set,
        notes=payload.notes,
        lines=[ln.model_dump() for ln in payload.lines]
        if payload.lines is not None
        else None,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**updated)


@router.post("/{po_id}/submit", response_model=PurchaseOrderOut)
def submit_purchase_order(
    po_id: int,
    request: Request,
    payload: PurchaseOrderApproveRequest | None = Body(default=None),
    actor: dict[str, Any] = Depends(require_any_permission(PO_CREATE, PO_ISSUE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    updated = po_service.submit_purchase_order(
        conn,
        actor=actor,
        po_id=po_id,
        notes=payload.notes if payload else None,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**updated)


@router.post("/{po_id}/approve", response_model=PurchaseOrderOut)
def approve_purchase_order(
    po_id: int,
    request: Request,
    payload: PurchaseOrderApproveRequest | None = Body(default=None),
    actor: dict[str, Any] = Depends(require_any_permission(PO_APPROVE_L1, PO_APPROVE_L2)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    updated = po_service.approve_purchase_order(
        conn,
        actor=actor,
        po_id=po_id,
        notes=payload.notes if payload else None,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**updated)


@router.post("/{po_id}/reject", response_model=PurchaseOrderOut)
def reject_purchase_order(
    po_id: int,
    payload: PurchaseOrderRejectRequest,
    request: Request,
    actor: dict[str, Any] = Depends(require_any_permission(PO_APPROVE_L1, PO_APPROVE_L2)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    updated = po_service.reject_purchase_order(
        conn,
        actor=actor,
        po_id=po_id,
        rejection_reason=payload.rejection_reason,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**updated)


@router.post("/{po_id}/issue", response_model=PurchaseOrderOut)
def issue_purchase_order(
    po_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(PO_APPROVE_L1)),
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


@router.post(
    "/{po_id}/revise-draft",
    response_model=PurchaseOrderOut,
    status_code=status.HTTP_201_CREATED,
)
def revise_purchase_order_as_draft(
    po_id: int,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(PO_CREATE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    revised = po_service.revise_issued_po_as_draft(
        conn,
        actor=actor,
        po_id=po_id,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**revised)


@router.post("/{po_id}/lines/{po_line_id}/close", response_model=PurchaseOrderOut)
def close_purchase_order_line(
    po_id: int,
    po_line_id: int,
    payload: PurchaseOrderCloseRequest,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(PO_CLOSE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> PurchaseOrderOut:
    updated = po_service.close_purchase_order_line(
        conn,
        actor=actor,
        po_id=po_id,
        po_line_id=po_line_id,
        closed_reason=payload.closed_reason,
        ip_address=get_client_ip(request),
    )
    return PurchaseOrderOut(**updated)

