"""Entrypoint utama FastAPI — lifespan connection pool, router, request ID, dan exception handler."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import (
    audit_logs,
    auth,
    dashboard,
    goods_receipts,
    health,
    master,
    menus,
    purchase_orders,
    stock,
    stock_opnames,
    stock_transfers,
    users,
    warehouses,
)
from app.core import database, telegram_alert
from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.logging import logger, request_id_ctx
from app.core.middleware import register_request_id_middleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Membuka dan menutup connection pool PostgreSQL sesuai siklus hidup aplikasi."""
    logger.info("Membuka connection pool database...")
    try:
        database.open_pool()
    except Exception as exc:
        logger.exception("Gagal membuka connection pool database saat startup: %s", exc)
        await telegram_alert.notify_exception_async(
            exc,
            http_status=None,
            source="lifespan/startup (database.open_pool)",
        )
        raise
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

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID"],
    )

    register_request_id_middleware(application)

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
                    "details": {"errors": jsonable_encoder(exc.errors())},
                }
            },
        )

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> Response:
        response = await http_exception_handler(request, exc)
        if exc.status_code >= 500:
            logger.error("Unhandled HTTP %s error: %s", exc.status_code, exc.detail)
            bg = telegram_alert.create_error_background_task(
                exc,
                request=request,
                http_status=exc.status_code,
            )
            if bg is not None:
                response.background = bg
        return response

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None) or request_id_ctx.get("-")
        token = request_id_ctx.set(req_id)
        try:
            logger.error("Unhandled internal error: %s", exc, exc_info=exc)
        finally:
            request_id_ctx.reset(token)

        headers = {"X-Request-ID": req_id} if req_id and req_id != "-" else None
        return JSONResponse(
            status_code=500,
            headers=headers,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Terjadi kesalahan internal pada server.",
                    "details": {},
                }
            },
            background=telegram_alert.create_error_background_task(
                exc,
                request=request,
                trace_id=req_id,
                http_status=500,
            ),
        )

    # Daftarkan endpoint health di root (/health, PRD 7.6) dan di bawah prefix /api/v1 (Lampiran B)
    application.include_router(health.router)
    application.include_router(health.router, prefix=settings.api_v1_prefix)

    # Daftarkan router domain di bawah prefix /api/v1
    application.include_router(auth.router, prefix=settings.api_v1_prefix)
    application.include_router(users.router, prefix=settings.api_v1_prefix)
    application.include_router(menus.router, prefix=settings.api_v1_prefix)
    application.include_router(master.router, prefix=settings.api_v1_prefix)
    application.include_router(warehouses.router, prefix=settings.api_v1_prefix)
    application.include_router(stock.router, prefix=settings.api_v1_prefix)
    application.include_router(purchase_orders.router, prefix=settings.api_v1_prefix)
    application.include_router(goods_receipts.router, prefix=settings.api_v1_prefix)
    application.include_router(stock_transfers.router, prefix=settings.api_v1_prefix)
    application.include_router(stock_opnames.router, prefix=settings.api_v1_prefix)
    application.include_router(audit_logs.router, prefix=settings.api_v1_prefix)
    application.include_router(dashboard.router, prefix=settings.api_v1_prefix)

    return application


app = create_app()
