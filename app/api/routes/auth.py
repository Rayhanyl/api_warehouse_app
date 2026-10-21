"""Routes Autentikasi: login, refresh, logout, me, dan change-password (FR-01, AC-11)."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from psycopg import Connection

from app.api.deps import get_client_ip, get_current_user
from app.core.database import get_conn
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


@router.post("/login", response_model=TokenOut)
def login(
    payload: LoginRequest,
    request: Request,
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> TokenOut:
    result = auth_service.login(
        conn,
        username=payload.username,
        password=payload.password,
        ip_address=get_client_ip(request),
    )
    return TokenOut(**result)


@router.post("/refresh", response_model=TokenOut)
def refresh_token(
    payload: RefreshTokenRequest,
    request: Request,
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> TokenOut:
    result = auth_service.refresh_session(
        conn,
        refresh_token=payload.refresh_token,
        ip_address=get_client_ip(request),
    )
    return TokenOut(**result)


@router.post("/logout", response_model=MessageOut)
def logout(
    payload: LogoutRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> MessageOut:
    auth_service.logout(
        conn,
        refresh_token=payload.refresh_token,
        actor=current_user,
        ip_address=get_client_ip(request),
    )
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

