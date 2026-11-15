"""Utilitas sanitasi data sensitif (password, token, koneksi DB, & PII) sebelum logging/alerting."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, quote_plus

_SENSITIVE_SINGLE_SEGMENTS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "authorization",
        "auth",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "jwt",
        "apikey",
        "signature",
        "email",
        "phone",
        "mobile",
        "telepon",
        "whatsapp",
        "alamat",
        "address",
        "nik",
        "npwp",
        "ktp",
    }
)

_SENSITIVE_PAIR_SEGMENTS: tuple[tuple[str, str], ...] = (
    ("api", "key"),
    ("private", "key"),
    ("access", "key"),
    ("secret", "key"),
    ("session", "id"),
    ("no", "hp"),
    ("e", "mail"),
    ("full", "name"),
    ("nama", "lengkap"),
)

# Pola URL dengan kredensial, mis. postgresql://user:secret@host:5432/db
_URL_CREDENTIAL_RE = re.compile(
    r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:/\s@]+:)([^\s/]+)(@[A-Za-z0-9._-]+)"
)

# Pola token bot Telegram, termasuk jika menempel tepat setelah prefix `bot` pada URL API Telegram
_TELEGRAM_BOT_TOKEN_RE = re.compile(r"(\bbot)?\d{6,15}:[A-Za-z0-9_-]{25,}\b")

# Pola JWT (header.payload.signature)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")

# Pola header Bearer / Basic
_AUTH_SCHEME_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{6,}")

# Pola key=value atau JSON/repr dengan nama field sensitif / PII
_KV_SENSITIVE_RE = re.compile(
    r"(?i)(\b[a-z0-9_.-]*(?:password|passwd|pwd|secret|token|authorization|cookie|"
    r"api_?key|private_key|credential|email|e-mail|phone|no_hp|telepon|alamat|"
    r"address|nik|npwp|ktp)[a-z0-9_.-]*[\"']?\s*[:=]\s*)"
    r"(?:\[REDACTED(?:_[A-Z0-9_]+)?\]|\"[^\"]*\"|'[^']*'|[^\s,;&}\]\)]+)"
)

# Pola detail constraint PostgreSQL: Key (email)=(user@domain.com) already exists
_PG_KEY_DETAIL_RE = re.compile(
    r"(?i)(Key\s*\([^)]*(?:email|phone|no_hp|nik|npwp|ktp|password|token|secret)[^)]*\)\s*=\s*\()([^)]+)(\))"
)

# Pola alamat email berdiri sendiri
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Pola nomor ponsel Indonesia berdiri sendiri (+62... atau 08...)
_ID_PHONE_RE = re.compile(r"(?<!\w)(?:\+62|08)\d[\d-]{6,13}\d(?!\w)")


_CREDENTIAL_SINGLE_SEGMENTS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "authorization",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "jwt",
        "apikey",
        "signature",
        "otp",
        "pin",
        "cvv",
    }
)

_CREDENTIAL_PAIR_SEGMENTS: tuple[tuple[str, str], ...] = (
    ("api", "key"),
    ("private", "key"),
    ("access", "key"),
    ("secret", "key"),
    ("session", "id"),
    ("csrf", "token"),
    ("xsrf", "token"),
    ("set", "cookie"),
)

_AUDIT_SAFE_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "password_changed",
        "revoked_refresh_tokens",
        "refresh_token_id",
        "previous_token_id",
        "new_token_id",
        "reused_token_id",
        "revoked_token_id",
    }
)


def is_sensitive_key(key: str) -> bool:
    """Mengembalikan True bila nama field/parameter mengindikasikan kredensial atau data pribadi."""
    segments = tuple(re.findall(r"[a-z0-9]+", key.lower()))
    if not segments:
        return False
    if any(seg in _SENSITIVE_SINGLE_SEGMENTS for seg in segments):
        return True
    segment_set = set(segments)
    return any(first in segment_set and second in segment_set for first, second in _SENSITIVE_PAIR_SEGMENTS)


def is_credential_key(key: str) -> bool:
    """Mengembalikan True bila nama field mengindikasikan kredensial/rahasia (aman untuk audit_logs master data)."""
    key_lower = key.strip().lower()
    if key_lower in _AUDIT_SAFE_METADATA_KEYS:
        return False
    segments = tuple(re.findall(r"[a-z0-9]+", key_lower))
    if not segments:
        return False
    if any(seg in _CREDENTIAL_SINGLE_SEGMENTS for seg in segments):
        return True
    segment_set = set(segments)
    return any(
        first in segment_set and second in segment_set
        for first, second in _CREDENTIAL_PAIR_SEGMENTS
    )


def sanitize_credential_text(text: str, *, max_length: int | None = None) -> str:
    """Menyamarkan password URL DB, token bot Telegram, JWT, dan header Bearer/Basic saja."""
    if not text:
        return ""
    cleaned = _URL_CREDENTIAL_RE.sub(r"\1[REDACTED]\3", text)
    cleaned = _TELEGRAM_BOT_TOKEN_RE.sub(
        lambda m: f"{m.group(1) or ''}[REDACTED_BOT_TOKEN]",
        cleaned,
    )
    cleaned = _JWT_RE.sub("[REDACTED_JWT]", cleaned)
    cleaned = _AUTH_SCHEME_RE.sub(r"\1 [REDACTED]", cleaned)
    if max_length is not None and len(cleaned) > max_length:
        suffix = "... [truncated]"
        cut = max(0, max_length - len(suffix))
        cleaned = f"{cleaned[:cut]}{suffix}"
    return cleaned


def sanitize_text(text: str, *, max_length: int | None = None) -> str:
    """Menyamarkan password, token, URL DB berkredensial, JWT, email, dan nomor telepon pada teks."""
    if not text:
        return ""

    cleaned = _URL_CREDENTIAL_RE.sub(r"\1[REDACTED]\3", text)
    cleaned = _TELEGRAM_BOT_TOKEN_RE.sub(
        lambda m: f"{m.group(1) or ''}[REDACTED_BOT_TOKEN]",
        cleaned,
    )
    cleaned = _JWT_RE.sub("[REDACTED_JWT]", cleaned)
    cleaned = _AUTH_SCHEME_RE.sub(r"\1 [REDACTED]", cleaned)
    cleaned = _PG_KEY_DETAIL_RE.sub(r"\1[REDACTED]\3", cleaned)
    cleaned = _KV_SENSITIVE_RE.sub(r"\1[REDACTED]", cleaned)
    cleaned = _EMAIL_RE.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _ID_PHONE_RE.sub("[REDACTED_PHONE]", cleaned)

    if max_length is not None and len(cleaned) > max_length:
        suffix = "... [truncated]"
        cut = max(0, max_length - len(suffix))
        cleaned = f"{cleaned[:cut]}{suffix}"
    return cleaned


def sanitize_url_path_and_query(path: str, query: str = "") -> str:
    """Membersihkan nilai sensitif pada path URL dan parameter query string."""
    safe_path = sanitize_text(path or "/")
    if not query:
        return safe_path

    sanitized_parts: list[str] = []
    for key, val in parse_qsl(query, keep_blank_values=True):
        safe_key = quote_plus(key)
        if is_sensitive_key(key):
            sanitized_parts.append(f"{safe_key}=[REDACTED]")
        else:
            cleaned_val = sanitize_text(val)
            encoded_val = (
                cleaned_val
                if cleaned_val.startswith("[REDACTED")
                else quote_plus(cleaned_val)
            )
            sanitized_parts.append(f"{safe_key}={encoded_val}")

    if not sanitized_parts:
        return safe_path
    return f"{safe_path}?{'&'.join(sanitized_parts)}"


def sanitize_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Menyaring field sensitif/PII dari kamus Python secara rekursif."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if is_sensitive_key(str(key)):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize_mapping(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_mapping(item)
                if isinstance(item, dict)
                else (sanitize_text(item) if isinstance(item, str) else item)
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = sanitize_text(value)
        else:
            result[key] = value
    return result
