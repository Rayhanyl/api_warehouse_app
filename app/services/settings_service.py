"""Service pengelolaan konfigurasi approval sistem (Tahap 34)."""

from decimal import Decimal, InvalidOperation
from typing import Any

from psycopg import Connection

from app.core.exceptions import ValidationDomainError
from app.repositories import settings_repo
from app.services import audit_service

DEFAULT_PO_L2_THRESHOLD = Decimal("10000000.00")


def _parse_threshold(raw: str | None) -> Decimal:
    if raw is None:
        return DEFAULT_PO_L2_THRESHOLD
    try:
        dec = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return DEFAULT_PO_L2_THRESHOLD
    if dec < Decimal("0"):
        return DEFAULT_PO_L2_THRESHOLD
    return dec.quantize(Decimal("0.01"))


def get_po_l2_threshold(conn: Connection[dict[str, Any]]) -> Decimal:
    """Mengembalikan nilai ambang batas nominal PO yang memerlukan persetujuan Level 2."""
    row = settings_repo.get_setting(conn, settings_repo.KEY_PO_L2_APPROVAL_THRESHOLD)
    return _parse_threshold(row["value"] if row else None)


def get_approval_settings(conn: Connection[dict[str, Any]]) -> dict[str, Any]:
    """Mengembalikan konfigurasi ambang approval PO saat ini."""
    row = settings_repo.get_setting(conn, settings_repo.KEY_PO_L2_APPROVAL_THRESHOLD)
    if row is None:
        return {
            "po_l2_approval_threshold": DEFAULT_PO_L2_THRESHOLD,
            "description": "Ambang nominal total PO (IDR); di atas nilai ini wajib persetujuan Level 2.",
            "updated_by": None,
            "updated_by_name": None,
            "updated_at": None,
        }
    return {
        "po_l2_approval_threshold": _parse_threshold(row["value"]),
        "description": row.get("description"),
        "updated_by": row.get("updated_by"),
        "updated_by_name": row.get("updated_by_name"),
        "updated_at": row.get("updated_at"),
    }


def update_approval_settings(
    conn: Connection[dict[str, Any]],
    *,
    po_l2_approval_threshold: Decimal,
    actor: dict[str, Any],
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Memperbarui ambang batas nominal PO untuk Level 2 approval secara atomik dan mencatat audit log."""
    if po_l2_approval_threshold < Decimal("0"):
        raise ValidationDomainError(
            "Ambang nominal approval PO tidak boleh negatif.",
            details={"field": "po_l2_approval_threshold"},
        )

    normalized = po_l2_approval_threshold.quantize(Decimal("0.01"))
    before = get_approval_settings(conn)

    with conn.transaction():
        saved = settings_repo.upsert_setting(
            conn,
            key=settings_repo.KEY_PO_L2_APPROVAL_THRESHOLD,
            value=f"{normalized:.2f}",
            updated_by=int(actor["id"]),
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="SETTINGS_UPDATED",
            entity_type="app_settings",
            entity_id=settings_repo.KEY_PO_L2_APPROVAL_THRESHOLD,
            old_values={"po_l2_approval_threshold": f"{before['po_l2_approval_threshold']:.2f}"},
            new_values={"po_l2_approval_threshold": f"{normalized:.2f}"},
            ip_address=ip_address,
        )

    return {
        "po_l2_approval_threshold": _parse_threshold(saved["value"]),
        "description": saved.get("description"),
        "updated_by": saved.get("updated_by"),
        "updated_by_name": saved.get("updated_by_name"),
        "updated_at": saved.get("updated_at"),
    }
