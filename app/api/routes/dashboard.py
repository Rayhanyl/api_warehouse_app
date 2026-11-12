"""Routes Dashboard operasional: GET /api/v1/dashboard/summary (DSH-F01, AC-38)."""

from typing import Any

from fastapi import APIRouter, Depends
from psycopg import Connection

from app.api.deps import get_current_user
from app.core.database import get_conn
from app.schemas.dashboard import DashboardSummaryOut
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    current_user: dict[str, Any] = Depends(get_current_user),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> DashboardSummaryOut:
    """Mengembalikan ringkasan metrik stok, tugas tertunda, dan mutasi terkini sesuai penugasan gudang."""
    result = dashboard_service.get_dashboard_summary(conn, actor=current_user)
    return DashboardSummaryOut(**result)
