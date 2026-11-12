"""Routes Autentikasi: login, refresh, logout, me, dan change-password (FR-01, AC-11, SEC-F01, CONF-008)."""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from psycopg import Connection

from app.api.deps import get_client_ip, get_current_user
from app.core.config import settings
from app.core.database import get_conn
from app.core.exceptions import AuthTokenInvalid
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    MeOut,
    MessageOut,
    RefreshTokenRequest,
    TokenOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Menyetel cookie HttpOnly refresh_token dengan flag keamanan tinggi (SEC-F01, CONF-008)."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/api/v1/auth",
        max_age=settings.refresh_token_days * 86400,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Menghapus cookie HttpOnly refresh_token pada peramban."""
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


@router.post("/login", response_model=TokenOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> TokenOut:
    result = auth_service.login(
        conn,
        username=payload.username,
        password=payload.password,
        ip_address=get_client_ip(request),
    )
    _set_refresh_cookie(response, result["refresh_token"])
    return TokenOut(**result)


@router.post("/refresh", response_model=TokenOut)
def refresh_token(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> TokenOut:
    token_str: str | None = None
    # 1. Jika dikirim via payload body eksplisit (klien API/CLI/tes reuse), prioritaskan payload
    if payload and payload.refresh_token and payload.refresh_token.strip():
        token_str = payload.refresh_token.strip()
    # 2. Jika tidak dikirim via body, baca dari cookie HttpOnly peramban
    elif "refresh_token" in request.cookies:
        token_str = request.cookies["refresh_token"].strip()

    if not token_str:
        raise AuthTokenInvalid("Refresh token tidak disediakan.")

    result = auth_service.refresh_session(
        conn,
        refresh_token=token_str,
        ip_address=get_client_ip(request),
    )
    _set_refresh_cookie(response, result["refresh_token"])
    return TokenOut(**result)


@router.post("/logout", response_model=MessageOut)
def logout(
    request: Request,
    response: Response,
    payload: LogoutRequest | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> MessageOut:
    token_str: str | None = None
    if payload and payload.refresh_token and payload.refresh_token.strip():
        token_str = payload.refresh_token.strip()
    elif "refresh_token" in request.cookies:
        token_str = request.cookies["refresh_token"].strip()

    if token_str:
        auth_service.logout(
            conn,
            refresh_token=token_str,
            actor=current_user,
            ip_address=get_client_ip(request),
        )

    _clear_refresh_cookie(response)
    return MessageOut(message="Logout berhasil; refresh token telah dicabut.")


@router.get("/me", response_model=MeOut)
def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> MeOut:
    return MeOut(**current_user)


@router.post("/change-password", response_model=MessageOut)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> MessageOut:
    auth_service.change_password(
        conn,
        actor=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        ip_address=get_client_ip(request),
    )
    return MessageOut(
        message="Kata sandi berhasil diperbarui dan seluruh sesi lama telah dicabut."
    )

