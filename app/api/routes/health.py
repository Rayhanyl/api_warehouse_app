"""Route pemeriksaan kesehatan layanan (PRD 7.6 & FR-01)."""

from typing import Any

from fastapi import APIRouter, Depends
from psycopg import Connection

from app.core.config import settings
from app.core.database import check_db_health, get_conn
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health(
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> HealthResponse:
    """Memeriksa status layanan API dan koneksi pool PostgreSQL."""
    db_ok = check_db_health(conn)
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        database="connected" if db_ok else "disconnected",
    )

