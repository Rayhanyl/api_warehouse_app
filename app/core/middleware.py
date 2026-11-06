"""Middleware request id untuk korelasi log & respons HTTP (PRD 6.6, API Contract §1.1, & AC-17)."""

import re
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, Response

from app.core.logging import request_id_ctx

REQUEST_ID_REGEX = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


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
        token = request_id_ctx.set(req_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)

