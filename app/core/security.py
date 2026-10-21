"""Fungsi keamanan: Argon2id password hashing, JWT Access Token, dan hash Refresh Token (FR-01, PRD 7.2)."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import jwt

from app.core.config import settings
from app.core.exceptions import AuthTokenInvalid

_ph = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Menghasilkan hash Argon2id dari kata sandi teks biasa."""
    return _ph.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Memverifikasi kata sandi terhadap hash Argon2id."""
    try:
        return _ph.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int) -> tuple[str, datetime]:
    """Menerbitkan JWT Access Token berumur ACCESS_TOKEN_MINUTES (15 menit) dengan klaim sub, jti, iat, exp."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    encoded = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return encoded, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    """Mendekode dan memvalidasi JWT Access Token; melempar AuthTokenInvalid bila tidak sah/kedaluwarsa."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "jti", "iat", "exp"]},
        )
        return payload
    except jwt.PyJWTError as exc:
        raise AuthTokenInvalid("Access token tidak valid atau sudah kedaluwarsa.") from exc


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Membuat Refresh Token acak opak beserta hash SHA-256 dan waktu kedaluwarsanya (7 hari)."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    return raw_token, token_hash, expires_at


def hash_refresh_token(raw_token: str) -> str:
    """Menghasilkan hash SHA-256 deterministik untuk pencarian Refresh Token di database."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

