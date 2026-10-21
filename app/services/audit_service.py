"""Service Audit Log: sanitasi data sensitif, pencatatan old_values/new_values, dan pembacaan log (FR-09)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from psycopg import Connection

from app.repositories import audit_repo
from app.utils.pagination import normalize_pagination

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "password_hash",
        "current_password",
        "new_password",
        "token",
        "token_hash",
        "access_token",
        "refresh_token",
    }
)


def _sanitize_payload(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Menghapus kunci rahasia (password, hash, token) dan menormalisasi nilai agar siap disimpan sebagai JSONB."""
    if data is None:
        return None

    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_KEYS:
            continue
        if isinstance(value, Decimal):
            cleaned[key] = f"{value:.4f}"
        elif isinstance(value, datetime):
            cleaned[key] = value.isoformat()
        elif isinstance(value, dict):
            cleaned[key] = _sanitize_payload(value)
        elif isinstance(value, list):
            cleaned[key] = [
                _sanitize_payload(item)
                if isinstance(item, dict)
                else (
                    f"{item:.4f}"
                    if isinstance(item, Decimal)
                    else (item.isoformat() if isinstance(item, datetime) else item)
                )
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned


def record(
    conn: Connection[dict[str, Any]],
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Mencatat satu entri ke tabel audit_logs setelah menyaring atribut sensitif (FR-09)."""
    return audit_repo.insert_audit_log(
        conn,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=_sanitize_payload(old_values),
        new_values=_sanitize_payload(new_values),
        ip_address=ip_address,
    )


def list_audit_logs(
    conn: Connection[dict[str, Any]],
    *,
    limit: int = 50,
    offset: int = 0,
    user_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    """Mengambil daftar audit log terpaginasi."""
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    items, total = audit_repo.list_audit_logs(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }

