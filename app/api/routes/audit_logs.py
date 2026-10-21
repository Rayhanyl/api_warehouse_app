"""Routes Audit Log (read-only, membutuhkan permission audit:read — FR-09 & Matriks 3.1 PRD)."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.core.database import get_conn
from app.core.permissions import AUDIT_READ, require_permission
from app.schemas.audit_log import AuditLogOut
from app.schemas.common import Page
from app.services import audit_service

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=Page[AuditLogOut])
def list_audit_logs(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(AUDIT_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[AuditLogOut]:
    page = audit_service.list_audit_logs(
        conn,
        limit=limit,
        offset=offset,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[AuditLogOut](**page)

