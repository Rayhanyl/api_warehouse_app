"""Dependencies HTTP: ekstraksi Bearer Token, verifikasi status aktif & role dari DB per request (FR-01, Invarian 14)."""

from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Connection

from app.core.database import get_conn
from app.core.exceptions import AuthTokenInvalid
from app.core.middleware import resolve_client_ip
from app.core.security import decode_access_token
from app.repositories import user_repo

bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str | None:
    """Mengambil alamat IP klien; X-Forwarded-For hanya dipercaya bila request berasal dari trusted_proxy_ips."""
    return resolve_client_ip(request)


def get_current_user(
    request: Request,
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

    request.state.actor = user
    return user
