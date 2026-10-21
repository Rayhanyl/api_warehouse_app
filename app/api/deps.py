"""Dependencies HTTP: ekstraksi Bearer Token, verifikasi status aktif & role dari DB per request (FR-01, Invarian 14)."""

from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Connection

from app.core.config import settings
from app.core.database import get_conn
from app.core.exceptions import AuthTokenInvalid
from app.core.security import decode_access_token
from app.repositories import user_repo

bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str | None:
    """Mengambil alamat IP klien; X-Forwarded-For hanya dipercaya bila request berasal dari trusted_proxy_ips."""
    client_host = request.client.host if request.client else None
    if client_host and client_host in settings.trusted_proxy_ips:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return client_host


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    """Memverifikasi JWT Access Token dan membaca ulang status aktif, role, permission, dan gudang dari database."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthTokenInvalid("Header Authorization Bearer token wajib disertakan.")

    payload = decode_access_token(credentials.credentials)
    sub = payload.get("sub")
    try:
        user_id = int(sub)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise AuthTokenInvalid("Subjek token tidak valid.") from exc

    user = user_repo.get_user_auth_context(conn, user_id)
    if not user or not user["is_active"]:
        raise AuthTokenInvalid("Akun pengguna tidak ditemukan atau sudah dinonaktifkan.")

    return user
