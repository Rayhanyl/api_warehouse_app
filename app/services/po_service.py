"""Service logika bisnis Purchase Order (PO) dan siklus statusnya (FR-04, PRD 5.1, 6.3, 6.9)."""

from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import Connection

from app.core.exceptions import (
    InactiveReferenceError,
    InvalidStateTransition,
    NotFoundError,
    PermissionDenied,
    ValidationDomainError,
)
from app.core.permissions import PO_CANCEL, PO_CREATE, ROLE_WAREHOUSE_STAFF
from app.repositories import inventory_repo, master_repo, po_repo, warehouse_repo
from app.services import access_service, audit_service, numbering_service
from app.utils.enums import DocType, POStatus
from app.utils.pagination import build_order_by, normalize_pagination

FOUR_PLACES = Decimal("0.0001")

PO_SORT_COLUMNS: dict[str, str] = {
    "id": "po.id",
    "po_number": "po.po_number",
    "order_date": "po.order_date",
    "status": "po.status",
    "created_at": "po.created_at",
}

ALLOWED_PO_STATUSES: frozenset[str] = frozenset(s.value for s in POStatus)


def _normalize_positive_qty(value: Decimal, *, field_name: str = "qty_ordered") -> Decimal:
    """Memastikan kuantitas bertipe Decimal > 0 dengan maksimum 4 angka di belakang koma (PRD 6.9)."""
    if isinstance(value, float):
        raise ValidationDomainError(
            f"Field '{field_name}' harus bertipe Decimal, tidak boleh float.",
            details={"field": field_name, "value": str(value)},
        )
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except Exception as exc:
            raise ValidationDomainError(
                f"Format angka desimal pada '{field_name}' tidak valid.",
                details={"field": field_name, "value": str(value)},
            ) from exc

    quantized = value.quantize(FOUR_PLACES)
    if quantized != value:
        raise ValidationDomainError(
            f"Field '{field_name}' maksimal memiliki 4 angka di belakang koma.",
            details={"field": field_name, "value": str(value)},
        )
    if quantized <= Decimal("0.0000"):
        raise ValidationDomainError(
            f"Field '{field_name}' harus lebih besar dari 0.",
            details={"field": field_name, "value": str(quantized)},
        )
    return quantized


def _validate_supplier_and_warehouse(
    conn: Connection[dict[str, Any]],
    *,
    supplier_id: int,
    warehouse_id: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Memastikan pemasok dan gudang tujuan ada dan berstatus aktif (PRD 5.1 & 6.3)."""
    supplier = master_repo.get_supplier_by_id(conn, supplier_id)
    if not supplier:
        raise NotFoundError(
            "Pemasok tidak ditemukan.",
            details={"supplier_id": supplier_id},
        )
    if not supplier["is_active"]:
        raise InactiveReferenceError(
            f"Pemasok '{supplier['name']}' berstatus tidak aktif.",
            details={"supplier_id": supplier_id, "supplier_code": supplier["code"]},
        )

    warehouse = warehouse_repo.get_warehouse_by_id(conn, warehouse_id)
    if not warehouse:
        raise NotFoundError(
            "Gudang tujuan tidak ditemukan.",
            details={"warehouse_id": warehouse_id},
        )
    if not warehouse["is_active"]:
        raise InactiveReferenceError(
            f"Gudang tujuan '{warehouse['name']}' berstatus tidak aktif.",
            details={"warehouse_id": warehouse_id, "warehouse_code": warehouse["code"]},
        )
    return supplier, warehouse


def _validate_and_normalize_po_lines(
    conn: Connection[dict[str, Any]],
    lines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Memvalidasi daftar baris PO: keunikan item per PO, status aktif barang, dan aturan UoM allow_decimal."""
    seen_item_ids: set[int] = set()
    normalized_lines: list[dict[str, Any]] = []

    for idx, line in enumerate(lines):
        item_id = int(line["item_id"])
        if item_id in seen_item_ids:
            raise ValidationDomainError(
                "Satu barang hanya boleh muncul satu kali dalam satu Purchase Order.",
                details={"duplicate_item_id": item_id, "line_index": idx},
            )
        seen_item_ids.add(item_id)

        qty_ordered = _normalize_positive_qty(
            line["qty_ordered"], field_name="qty_ordered"
        )

        item = inventory_repo.get_item_with_uom(conn, item_id)
        if not item:
            raise NotFoundError(
                "Barang pada baris Purchase Order tidak ditemukan.",
                details={"item_id": item_id, "line_index": idx},
            )
        if not item["is_active"]:
            raise InactiveReferenceError(
                f"Barang '{item['sku']}' berstatus tidak aktif.",
                details={"item_id": item_id, "sku": item["sku"], "line_index": idx},
            )
        if not bool(item["allow_decimal"]) and qty_ordered != qty_ordered.to_integral_value():
            raise ValidationDomainError(
                f"Barang '{item['sku']}' menggunakan UoM '{item['uom_code']}' yang harus berupa bilangan bulat.",
                details={
                    "item_id": item_id,
                    "sku": item["sku"],
                    "uom_code": item["uom_code"],
                    "qty_ordered": str(qty_ordered),
                    "line_index": idx,
                },
            )

        clean_notes = (
            line["notes"].strip()
            if line.get("notes") is not None and str(line["notes"]).strip()
            else None
        )
        normalized_lines.append(
            {
                "item_id": item_id,
                "qty_ordered": qty_ordered,
                "notes": clean_notes,
            }
        )

    return normalized_lines


def _serialize_po_snapshot(po_detail: dict[str, Any]) -> dict[str, Any]:
    """Menyusun representasi ringkas PO untuk old_values/new_values di audit_logs."""
    return {
        "id": po_detail["id"],
        "po_number": po_detail["po_number"],
        "supplier_id": po_detail["supplier_id"],
        "warehouse_id": po_detail["warehouse_id"],
        "status": po_detail["status"],
        "order_date": po_detail["order_date"].isoformat()
        if isinstance(po_detail["order_date"], date)
        else str(po_detail["order_date"]),
        "notes": po_detail["notes"],
        "closed_reason": po_detail.get("closed_reason"),
        "lines": [
            {
                "id": ln["id"],
                "item_id": ln["item_id"],
                "item_sku": ln["item_sku"],
                "qty_ordered": f"{Decimal(ln['qty_ordered']):.4f}",
                "qty_received": f"{Decimal(ln['qty_received']):.4f}",
                "notes": ln.get("notes"),
            }
            for ln in po_detail.get("lines", [])
        ],
    }


def list_purchase_orders(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    warehouse_id: int | None = None,
    supplier_id: int | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=PO_SORT_COLUMNS,
        default_column="id",
        default_dir="DESC",
    )

    clean_status: str | None = None
    if status is not None:
        clean_status = status.strip().upper()
        if clean_status not in ALLOWED_PO_STATUSES:
            raise ValidationDomainError(
                f"Filter status PO '{status}' tidak valid.",
                details={
                    "status": status,
                    "allowed_values": sorted(ALLOWED_PO_STATUSES),
                },
            )

    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValidationDomainError(
            "Parameter date_from tidak boleh lebih besar dari date_to.",
            details={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            },
        )

    # PRD 3.2 poin 5 & 6: Warehouse Staff hanya melihat dokumen pada gudang yang ditugaskan
    scoped_ids = access_service.get_scoped_warehouse_ids_for_read(conn, actor)
    if scoped_ids is not None and warehouse_id is not None:
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

    items, total = po_repo.list_purchase_orders(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        scoped_warehouse_ids=scoped_ids,
        warehouse_id=warehouse_id,
        supplier_id=supplier_id,
        status=clean_status,
        date_from=date_from,
        date_to=date_to,
        search=search,
        order_by_sql=order_by_sql,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def get_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
) -> dict[str, Any]:
    po = po_repo.get_po_by_id(conn, po_id)
    if not po:
        raise NotFoundError(
            "Purchase Order tidak ditemukan.",
            details={"po_id": po_id},
        )
    if actor.get("role_name") == ROLE_WAREHOUSE_STAFF:
        access_service.ensure_warehouse_access(conn, actor, int(po["warehouse_id"]))
    return po


def create_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    supplier_id: int,
    warehouse_id: int,
    order_date: date,
    notes: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    clean_notes = notes.strip() if notes is not None and notes.strip() else None

    with conn.transaction():
        _validate_supplier_and_warehouse(
            conn, supplier_id=supplier_id, warehouse_id=warehouse_id
        )
        normalized_lines = _validate_and_normalize_po_lines(conn, lines or [])

        po_number = numbering_service.generate_document_number(
            conn, DocType.PO, reference_date=order_date
        )
        header = po_repo.insert_po_header(
            conn,
            po_number=po_number,
            supplier_id=supplier_id,
            warehouse_id=warehouse_id,
            order_date=order_date,
            notes=clean_notes,
            created_by=int(actor["id"]),
        )
        po_id = int(header["id"])

        if normalized_lines:
            po_repo.replace_po_lines(
                conn,
                po_id=po_id,
                lines=normalized_lines,
                actor_id=int(actor["id"]),
            )

        created = po_repo.get_po_by_id(conn, po_id)
        assert created is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_CREATED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values=None,
            new_values=_serialize_po_snapshot(created),
            ip_address=ip_address,
        )
        return created


def update_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    supplier_id: int | None = None,
    warehouse_id: int | None = None,
    order_date: date | None = None,
    notes: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )
        if locked["status"] != POStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Purchase Order berstatus '{locked['status']}' tidak dapat diubah; hanya PO berstatus DRAFT yang dapat direvisi.",
                details={"po_id": po_id, "current_status": locked["status"]},
            )

        before_detail = po_repo.get_po_by_id(conn, po_id)
        assert before_detail is not None
        old_snapshot = _serialize_po_snapshot(before_detail)

        new_supplier_id = (
            int(supplier_id)
            if supplier_id is not None
            else int(locked["supplier_id"])
        )
        new_warehouse_id = (
            int(warehouse_id)
            if warehouse_id is not None
            else int(locked["warehouse_id"])
        )
        _validate_supplier_and_warehouse(
            conn, supplier_id=new_supplier_id, warehouse_id=new_warehouse_id
        )

        new_order_date = (
            order_date if order_date is not None else locked["order_date"]
        )
        new_notes = (
            (notes.strip() if notes.strip() else None)
            if notes is not None
            else locked["notes"]
        )

        po_repo.update_po_draft_header(
            conn,
            po_id,
            supplier_id=new_supplier_id,
            warehouse_id=new_warehouse_id,
            order_date=new_order_date,
            notes=new_notes,
        )

        if lines is not None:
            normalized_lines = _validate_and_normalize_po_lines(conn, lines)
            po_repo.replace_po_lines(
                conn,
                po_id=po_id,
                lines=normalized_lines,
                actor_id=int(actor["id"]),
            )

        updated = po_repo.get_po_by_id(conn, po_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_UPDATED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values=old_snapshot,
            new_values=_serialize_po_snapshot(updated),
            ip_address=ip_address,
        )
        return updated


def issue_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Transisi DRAFT -> ISSUED (PRD 5.1, po:issue)."""
    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )
        if locked["status"] != POStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Purchase Order berstatus '{locked['status']}' tidak dapat diterbitkan (harus berstatus DRAFT).",
                details={
                    "po_id": po_id,
                    "current_status": locked["status"],
                    "target_status": POStatus.ISSUED.value,
                },
            )

        _validate_supplier_and_warehouse(
            conn,
            supplier_id=int(locked["supplier_id"]),
            warehouse_id=int(locked["warehouse_id"]),
        )

        po_repo.lock_po_lines(conn, po_id)
        lines = po_repo.list_po_lines(conn, po_id)
        if not lines:
            raise ValidationDomainError(
                "Purchase Order tidak dapat diterbitkan karena belum memiliki baris barang.",
                details={"po_id": po_id},
            )

        for ln in lines:
            qty_ordered = _normalize_positive_qty(
                Decimal(ln["qty_ordered"]), field_name="qty_ordered"
            )
            if not ln["item_is_active"]:
                raise InactiveReferenceError(
                    f"Barang '{ln['item_sku']}' pada baris PO berstatus tidak aktif.",
                    details={"po_id": po_id, "item_id": ln["item_id"], "sku": ln["item_sku"]},
                )
            if not bool(ln["allow_decimal"]) and qty_ordered != qty_ordered.to_integral_value():
                raise ValidationDomainError(
                    f"Barang '{ln['item_sku']}' menggunakan UoM '{ln['uom_code']}' yang harus berupa bilangan bulat.",
                    details={
                        "po_id": po_id,
                        "item_id": ln["item_id"],
                        "qty_ordered": str(qty_ordered),
                    },
                )

        po_repo.update_po_issued(conn, po_id, issued_by=int(actor["id"]))
        updated = po_repo.get_po_by_id(conn, po_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_ISSUED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values={"status": POStatus.DRAFT.value},
            new_values={
                "status": POStatus.ISSUED.value,
                "issued_by": updated["issued_by"],
                "issued_at": updated["issued_at"].isoformat()
                if updated["issued_at"]
                else None,
            },
            ip_address=ip_address,
        )
        return updated


def cancel_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Transisi DRAFT -> CANCELLED (po:create) atau ISSUED -> CANCELLED (po:cancel) sesuai PRD 5.1."""
    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )

        current_status = str(locked["status"])
        actor_perms: set[str] = set(actor.get("permissions", []))

        if current_status == POStatus.DRAFT.value:
            if PO_CREATE not in actor_perms:
                raise PermissionDenied(
                    f"Anda tidak memiliki izin '{PO_CREATE}' untuk membatalkan PO berstatus DRAFT.",
                    details={"required_permission": PO_CREATE},
                )
        elif current_status == POStatus.ISSUED.value:
            if PO_CANCEL not in actor_perms:
                raise PermissionDenied(
                    f"Anda tidak memiliki izin '{PO_CANCEL}' untuk membatalkan PO berstatus ISSUED.",
                    details={"required_permission": PO_CANCEL},
                )
            if po_repo.has_draft_or_posted_gr_for_po(conn, po_id):
                raise InvalidStateTransition(
                    "Purchase Order berstatus ISSUED tidak dapat dibatalkan karena sudah memiliki Goods Receipt berstatus DRAFT atau POSTED.",
                    details={"po_id": po_id, "current_status": current_status},
                )
        else:
            raise InvalidStateTransition(
                f"Purchase Order berstatus '{current_status}' tidak dapat dibatalkan.",
                details={
                    "po_id": po_id,
                    "current_status": current_status,
                    "target_status": POStatus.CANCELLED.value,
                },
            )

        po_repo.update_po_cancelled(conn, po_id)
        updated = po_repo.get_po_by_id(conn, po_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_CANCELLED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values={"status": current_status},
            new_values={"status": POStatus.CANCELLED.value},
            ip_address=ip_address,
        )
        return updated


def close_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    closed_reason: str,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Transisi ISSUED / PARTIALLY_RECEIVED -> CLOSED (PRD 5.1, po:close)."""
    clean_reason = closed_reason.strip() if closed_reason else ""
    if not clean_reason:
        raise ValidationDomainError(
            "Alasan penutupan Purchase Order (closed_reason) wajib diisi.",
            details={"field": "closed_reason"},
        )

    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )

        current_status = str(locked["status"])
        if current_status not in (
            POStatus.ISSUED.value,
            POStatus.PARTIALLY_RECEIVED.value,
        ):
            raise InvalidStateTransition(
                f"Purchase Order berstatus '{current_status}' tidak dapat ditutup (harus ISSUED atau PARTIALLY_RECEIVED).",
                details={
                    "po_id": po_id,
                    "current_status": current_status,
                    "target_status": POStatus.CLOSED.value,
                },
            )

        if po_repo.has_draft_gr_for_po(conn, po_id):
            raise InvalidStateTransition(
                "Purchase Order tidak dapat ditutup karena masih memiliki Goods Receipt berstatus DRAFT.",
                details={"po_id": po_id, "current_status": current_status},
            )

        po_repo.update_po_closed(
            conn,
            po_id,
            closed_reason=clean_reason,
            closed_by=int(actor["id"]),
        )
        updated = po_repo.get_po_by_id(conn, po_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_CLOSED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values={"status": current_status},
            new_values={
                "status": POStatus.CLOSED.value,
                "closed_reason": clean_reason,
                "closed_by": updated["closed_by"],
                "closed_at": updated["closed_at"].isoformat()
                if updated["closed_at"]
                else None,
            },
            ip_address=ip_address,
        )
        return updated

