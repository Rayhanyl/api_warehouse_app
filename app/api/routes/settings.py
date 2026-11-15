"""Routes konfigurasi sistem & ambang approval (Tahap 34)."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from psycopg import Connection

from app.api.deps import get_client_ip, get_current_user
from app.core.database import get_conn
from app.core.permissions import SETTINGS_MANAGE, require_permission
from app.schemas.settings import ApprovalSettingsOut, ApprovalSettingsUpdate
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/approval", response_model=ApprovalSettingsOut)
def get_approval_settings(
    _actor: dict[str, Any] = Depends(get_current_user),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> ApprovalSettingsOut:
    """Membaca ambang nominal persetujuan PO Level 2 (dapat dibaca pengguna terautentikasi untuk tampilan UI)."""
    data = settings_service.get_approval_settings(conn)
    return ApprovalSettingsOut(**data)


@router.put("/approval", response_model=ApprovalSettingsOut)
def update_approval_settings(
    payload: ApprovalSettingsUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(SETTINGS_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> ApprovalSettingsOut:
    """Memperbarui ambang nominal persetujuan PO Level 2 (khusus Super Admin / pemegang settings:manage)."""
    updated = settings_service.update_approval_settings(
        conn,
        po_l2_approval_threshold=payload.po_l2_approval_threshold,
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return ApprovalSettingsOut(**updated)
