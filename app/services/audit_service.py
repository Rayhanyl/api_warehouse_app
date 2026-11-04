"""Service Audit Log: sanitasi data sensitif, pencatatan diff old_values/new_values, dan pembacaan log (FR-09)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from psycopg import Connection

from app.core.exceptions import ValidationDomainError
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

IGNORED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "created_at",
        "updated_at",
    }
)


def _sanitize_payload(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Menghapus kunci rahasia (password, hash, token), metadata waktu, dan menormalisasi nilai untuk JSONB."""
    if data is None:
        return None

    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()
        if key_lower in SENSITIVE_KEYS or key_lower in IGNORED_METADATA_KEYS:
            continue
        if isinstance(value, Decimal):
            cleaned[key] = f"{value:.4f}"
        elif isinstance(value, (datetime, date)):
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
                    else (
                        item.isoformat()
                        if isinstance(item, (datetime, date))
                        else item
                    )
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
) -> dict[str, Any] | None:
    """Mencatat satu entri ke tabel audit_logs setelah menyaring atribut sensitif (FR-09).

    Untuk aksi perubahan (saat old_values dan new_values keduanya diberikan):
    - Jika tidak ada perubahan nilai bisnis sama sekali (no-op update), tidak menyisipkan baris duplikat.
    - Hanya menyimpan field yang benar-benar berubah (diff) agar ukuran JSONB tetap ringkas.
    """
    clean_old = _sanitize_payload(old_values)
    clean_new = _sanitize_payload(new_values)

    if clean_old is not None and clean_new is not None:
        changed_keys = sorted(
            k
            for k in (clean_old.keys() | clean_new.keys())
            if clean_old.get(k) != clean_new.get(k)
        )
        if not changed_keys:
            return None
        clean_old = {k: clean_old.get(k) for k in changed_keys}
        clean_new = {k: clean_new.get(k) for k in changed_keys}

    return audit_repo.insert_audit_log(
        conn,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=clean_old,
        new_values=clean_new,
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
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    """Mengambil daftar audit log terpaginasi."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValidationDomainError(
            "Rentang tanggal tidak valid: date_from tidak boleh lebih besar dari date_to.",
            details={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            },
        )
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
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }
