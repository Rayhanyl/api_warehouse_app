"""Route pemeriksaan kesehatan layanan (PRD 7.6 & FR-01)."""

from fastapi import APIRouter

from app.core.config import settings
from app.core.database import check_pool_health
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Memeriksa status layanan API dan koneksi pool PostgreSQL."""
    db_ok = check_pool_health()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        database="connected" if db_ok else "disconnected",
    )
