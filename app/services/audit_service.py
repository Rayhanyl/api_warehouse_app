"""Service Audit Log: sanitasi data sensitif, diff old/new, konteks HTTP, pencatatan gagal, & pembacaan (FR-09, Tahap 14)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Request
from psycopg import Connection

from app.core import database
from app.core.exceptions import ValidationDomainError
from app.core.logging import audit_context_ctx, logger, request_id_ctx
from app.core.sanitizer import (
    is_credential_key,
    sanitize_credential_text,
    sanitize_url_path_and_query,
)
from app.repositories import audit_repo
from app.utils.pagination import normalize_pagination

VALID_AUDIT_STATUSES: frozenset[str] = frozenset({"SUCCESS", "FAILED"})

IGNORED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "created_at",
        "updated_at",
    }
)

_RESOURCE_ENTITY_MAP: dict[str, str] = {
    "auth": "users",
    "users": "users",
    "roles": "roles",
    "menus": "menus",
    "categories": "categories",
    "uoms": "uoms",
    "suppliers": "suppliers",
    "items": "items",
    "warehouses": "warehouses",
    "locations": "storage_locations",
    "purchase-orders": "purchase_orders",
    "goods-receipts": "goods_receipts",
    "stock-transfers": "stock_transfers",
    "stock-opnames": "stock_opnames",
    "stock": "stock_balances",
    "audit-logs": "audit_logs",
}


def _sanitize_value(value: Any) -> Any:
    """Menormalisasi nilai tunggal dan menyamarkan teks kredensial/token jika muncul di dalam string."""
    if isinstance(value, Decimal):
        return f"{value:.4f}"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return _sanitize_payload(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return sanitize_credential_text(value)
    return value


def _sanitize_payload(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Menghapus kunci rahasia/kredensial, metadata waktu, dan menormalisasi nilai untuk JSONB."""
    if data is None:
        return None

    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        key_str = str(key)
        key_lower = key_str.lower()
        if key_lower in IGNORED_METADATA_KEYS or is_credential_key(key_str):
            continue
        cleaned[key_str] = _sanitize_value(value)
    return cleaned


def _normalize_status(status: str | None) -> str:
    norm = (status or "SUCCESS").strip().upper()
    if norm not in VALID_AUDIT_STATUSES:
        raise ValidationDomainError(
            "Status audit tidak valid. Gunakan 'SUCCESS' atau 'FAILED'.",
            details={"status": status},
        )
    return norm


def _resolve_request_metadata(
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Mengisi metadata konteks HTTP dari ContextVar jika parameter belum diberikan secara eksplisit."""
    ctx = audit_context_ctx.get({})
    resolved_ip = ip_address if ip_address is not None else ctx.get("ip_address")
    raw_ua = user_agent if user_agent is not None else ctx.get("user_agent")
    resolved_ua = (
        sanitize_credential_text(raw_ua.strip(), max_length=512)[:512]
        if raw_ua and raw_ua.strip()
        else None
    )
    resolved_req_id = (
        request_id
        if request_id is not None
        else ctx.get("request_id") or request_id_ctx.get("-")
    )
    if resolved_req_id == "-":
        resolved_req_id = None
    elif resolved_req_id:
        resolved_req_id = resolved_req_id[:128]
    return resolved_ip, resolved_ua, resolved_req_id


def infer_entity_from_path(path: str) -> tuple[str, str | None]:
    """Menebak entity_type dan entity_id secara konsisten dari path REST API."""
    segments = [seg for seg in path.strip("/").split("/") if seg]
    if len(segments) >= 2 and segments[0] == "api" and segments[1] == "v1":
        segments = segments[2:]

    if not segments:
        return "system", None

    # Kasus khusus nested route: /warehouses/{id}/locations/{loc_id} & /users/{id}/warehouses & /users/roles/{id}/permissions
    if segments[0] == "warehouses" and "locations" in segments:
        loc_idx = segments.index("locations")
        loc_id = (
            segments[loc_idx + 1]
            if loc_idx + 1 < len(segments) and segments[loc_idx + 1].isdigit()
            else None
        )
        return "storage_locations", loc_id
    if segments[0] == "users" and "warehouses" in segments:
        uid = segments[1] if len(segments) > 1 and segments[1].isdigit() else None
        return "user_warehouses", uid
    if segments[0] == "users" and "roles" in segments:
        role_idx = segments.index("roles")
        rid = (
            segments[role_idx + 1]
            if role_idx + 1 < len(segments) and segments[role_idx + 1].isdigit()
            else None
        )
        return "roles", rid
    if segments[0] == "auth":
        if "refresh" in segments or "logout" in segments:
            return "refresh_tokens", None
        return "users", None

    entity_type = _RESOURCE_ENTITY_MAP.get(segments[0], segments[0].replace("-", "_"))
    entity_id = (
        segments[1] if len(segments) > 1 and segments[1].isdigit() else None
    )
    return entity_type, entity_id


def sanitize_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Menyaring payload validation error Pydantic agar tidak menyimpan raw password/token."""
    safe_errors: list[dict[str, Any]] = []
    for err in errors[:10]:
        loc = err.get("loc", ())
        loc_has_secret = any(is_credential_key(str(part)) for part in loc)
        item: dict[str, Any] = {
            "loc": [str(part) for part in loc],
            "msg": sanitize_credential_text(str(err.get("msg", "")), max_length=250),
            "type": str(err.get("type", "")),
        }
        if not loc_has_secret and "input" in err:
            raw_input = err["input"]
            if isinstance(raw_input, dict):
                item["input"] = _sanitize_payload(raw_input)
            elif isinstance(raw_input, str):
                item["input"] = sanitize_credential_text(raw_input, max_length=120)
        safe_errors.append(item)
    return safe_errors


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
    status: str = "SUCCESS",
    details: dict[str, Any] | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    """Mencatat satu entri ke tabel audit_logs setelah menyaring atribut sensitif (FR-09 & Tahap 14).

    Untuk aksi berhasil (status='SUCCESS') dengan old_values & new_values:
    - Jika tidak ada perubahan nilai bisnis sama sekali (no-op update), tidak menyisipkan baris duplikat.
    - Hanya menyimpan field yang benar-benar berubah (diff) agar ukuran JSONB tetap ringkas.
    Untuk aksi gagal (status='FAILED'), baris selalu dicatat agar jejak kegagalan tidak terlewat.
    """
    norm_status = _normalize_status(status)
    clean_old = _sanitize_payload(old_values)
    clean_new = _sanitize_payload(new_values)
    clean_details = _sanitize_payload(details)

    if norm_status == "SUCCESS" and clean_old is not None and clean_new is not None:
        changed_keys = sorted(
            k
            for k in (clean_old.keys() | clean_new.keys())
            if clean_old.get(k) != clean_new.get(k)
        )
        if not changed_keys:
            return None
        clean_old = {k: clean_old.get(k) for k in changed_keys}
        clean_new = {k: clean_new.get(k) for k in changed_keys}

    resolved_ip, resolved_ua, resolved_req_id = _resolve_request_metadata(
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )

    return audit_repo.insert_audit_log(
        conn,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=clean_old,
        new_values=clean_new,
        ip_address=resolved_ip,
        status=norm_status,
        details=clean_details,
        user_agent=resolved_ua,
        request_id=resolved_req_id,
    )


def record_many(conn: Connection[dict[str, Any]], events: list[dict[str, Any]]) -> None:
    """Sanitasi dan tulis beberapa event audit dalam satu operasi repository batch."""
    cleaned_events: list[dict[str, Any]] = []
    for event in events:
        resolved_ip, resolved_ua, resolved_req_id = _resolve_request_metadata(
            ip_address=event.get("ip_address"),
            user_agent=event.get("user_agent"),
            request_id=event.get("request_id"),
        )
        cleaned_events.append(
            {
                "user_id": event["user_id"],
                "action": event["action"],
                "entity_type": event["entity_type"],
                "entity_id": event["entity_id"],
                "old_values": _sanitize_payload(event.get("old_values")),
                "new_values": _sanitize_payload(event.get("new_values")),
                "status": _normalize_status(event.get("status")),
                "details": _sanitize_payload(event.get("details")),
                "ip_address": resolved_ip,
                "user_agent": resolved_ua,
                "request_id": resolved_req_id,
            }
        )
    audit_repo.insert_audit_logs_batch(conn, cleaned_events)


def record_http_failure(
    request: Request,
    *,
    action: str,
    error_code: str,
    http_status: int,
    message: str,
    error_details: dict[str, Any] | None = None,
) -> None:
    """Mencatat kegagalan request API di luar transaksi bisnis yang telah rollback (best-effort)."""
    if database.pool.closed:
        return

    actor = getattr(request.state, "actor", None)
    user_id = int(actor["id"]) if isinstance(actor, dict) and actor.get("id") else None
    entity_type, entity_id = infer_entity_from_path(request.url.path)

    client_ip = getattr(request.state, "client_ip", None)
    user_agent = getattr(request.state, "user_agent", None)
    req_id = getattr(request.state, "request_id", None) or request_id_ctx.get("-")
    if req_id == "-":
        req_id = None

    safe_path = sanitize_url_path_and_query(request.url.path, "")
    detail_payload: dict[str, Any] = {
        "error_code": error_code,
        "http_status": http_status,
        "method": request.method,
        "path": safe_path,
        "message": sanitize_credential_text(message, max_length=300),
    }
    if error_details:
        detail_payload["error_details"] = _sanitize_payload(error_details)

    try:
        with database.pool.connection(timeout=2.0) as conn:
            with conn.transaction():
                record(
                    conn,
                    user_id=user_id,
                    action=action[:100],
                    entity_type=entity_type[:100],
                    entity_id=entity_id,
                    ip_address=client_ip,
                    status="FAILED",
                    details=detail_payload,
                    user_agent=user_agent,
                    request_id=req_id,
                )
    except Exception as exc:
        logger.warning(
            "Gagal mencatat audit log kegagalan HTTP (%s %s): %s",
            request.method,
            safe_path,
            exc,
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
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    """Mengambil daftar audit log terpaginasi."""
    norm_status: str | None = None
    if status is not None and status.strip():
        norm_status = _normalize_status(status)

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
        status=norm_status,
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
