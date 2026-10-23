"""Entrypoint utama FastAPI — lifespan connection pool, router, request ID, dan exception handler."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import audit_logs, auth, health, master, stock, users, warehouses
from app.core import database
from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.logging import logger, request_id_ctx


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Membuka dan menutup connection pool PostgreSQL sesuai siklus hidup aplikasi."""
    logger.info("Membuka connection pool database...")
    database.open_pool()
    logger.info("Connection pool database siap digunakan.")
    try:
        yield
    finally:
        logger.info("Menutup connection pool database...")
        database.close_pool()
        logger.info("Connection pool database ditutup.")


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Warehouse Management System (WMS) REST API — FastAPI + PostgreSQL (psycopg 3)",
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(req_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)

    @application.exception_handler(DomainError)
    def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.http_status == 401 else None
        return JSONResponse(
            status_code=exc.http_status,
            headers=headers,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Payload permintaan tidak valid.",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @application.exception_handler(Exception)
    def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled internal error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Terjadi kesalahan internal pada server.",
                    "details": {},
                }
            },
        )

    # Daftarkan endpoint health di root (/health, PRD 7.6) dan di bawah prefix /api/v1 (Lampiran B)
    application.include_router(health.router)
    application.include_router(health.router, prefix=settings.api_v1_prefix)

    # Daftarkan router domain di bawah prefix /api/v1
    application.include_router(auth.router, prefix=settings.api_v1_prefix)
    application.include_router(users.router, prefix=settings.api_v1_prefix)
    application.include_router(master.router, prefix=settings.api_v1_prefix)
    application.include_router(warehouses.router, prefix=settings.api_v1_prefix)
    application.include_router(stock.router, prefix=settings.api_v1_prefix)
    application.include_router(audit_logs.router, prefix=settings.api_v1_prefix)

    return application


app = create_app()
