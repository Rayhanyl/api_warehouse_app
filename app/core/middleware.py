"""Middleware request id & konteks audit HTTP (PRD 6.6, API Contract §1.1, AC-17, & Tahap 14)."""

import re
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, Response

from app.core.config import settings
from app.core.logging import audit_context_ctx, request_id_ctx
from app.core.sanitizer import sanitize_credential_text

REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def resolve_client_ip(request: Request) -> str | None:
    """Mengambil alamat IP klien; X-Forwarded-For hanya dipercaya bila request berasal dari trusted_proxy_ips."""
    client_host = request.client.host if request.client else None
    if client_host and client_host in settings.trusted_proxy_ips:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return client_host


def extract_user_agent(request: Request) -> str | None:
    """Mengambil User-Agent secara aman (disanitasi dari kredensial/token dan dibatasi 512 karakter)."""
    raw_ua = request.headers.get("User-Agent", "").strip()
    if not raw_ua:
        return None
    return sanitize_credential_text(raw_ua, max_length=512)[:512]


def register_request_id_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        supplied_req_id = request.headers.get("X-Request-ID", "").strip()
        req_id = (
            supplied_req_id
            if REQUEST_ID_REGEX.match(supplied_req_id)
            else str(uuid.uuid4())
        )
        client_ip = resolve_client_ip(request)
        user_agent = extract_user_agent(request)

        req_token = request_id_ctx.set(req_id)
        audit_token = audit_context_ctx.set(
            {
                "ip_address": client_ip,
                "user_agent": user_agent,
                "request_id": req_id,
            }
        )
        request.state.request_id = req_id
        request.state.client_ip = client_ip
        request.state.user_agent = user_agent
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            audit_context_ctx.reset(audit_token)
            request_id_ctx.reset(req_token)

