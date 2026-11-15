"""Route pemeriksaan kesehatan layanan (PRD 7.6 & FR-01)."""

from fastapi import APIRouter

from app.core.config import settings
from app.core.database import check_schema_health
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Memeriksa status layanan API, koneksi pool PostgreSQL, dan kesiapan migrasi skema."""
    db_ok, pending = check_schema_health()
    if not db_ok:
        schema_status = "unknown"
    elif pending:
        schema_status = "pending_migrations"
    else:
        schema_status = "ok"

    return HealthResponse(
        status="ok" if (db_ok and not pending) else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        database="connected" if db_ok else "disconnected",
        schema_status=schema_status,
        pending_migrations=pending,
    )
