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
from app.core.permissions import (
    PO_APPROVE_L1,
    PO_APPROVE_L2,
    PO_CANCEL,
    PO_CREATE,
    check_sod_actor,
)
from app.core.validation import (
    FOUR_PLACES,
    MAX_QTY,
    clean_optional_str,
    normalize_decimal_qty,
)
from app.repositories import (
    approval_repo,
    inventory_repo,
    master_repo,
    po_repo,
    warehouse_repo,
)
from app.services import (
    access_service,
    audit_service,
    numbering_service,
    settings_service,
)
from app.utils.enums import DocType, POStatus
from app.utils.pagination import build_order_by, normalize_pagination

PO_SORT_COLUMNS: dict[str, str] = {
    "id": "po.id",
    "po_number": "po.po_number",
    "order_date": "po.order_date",
    "expected_delivery_date": "po.expected_delivery_date",
    "status": "po.status",
    "created_at": "po.created_at",
}

ALLOWED_PO_STATUSES: frozenset[str] = frozenset(s.value for s in POStatus)


def _normalize_positive_qty(value: Decimal, *, field_name: str = "qty_ordered") -> Decimal:
    """Memastikan kuantitas bertipe Decimal > 0 dengan maksimum 4 angka di belakang koma (PRD 6.9)."""
    return normalize_decimal_qty(value, field_name=field_name, allow_zero=False)


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
        raw_price = line.get("unit_price")
        unit_price = (
            Decimal("0.00")
            if raw_price is None or raw_price == ""
            else Decimal(str(raw_price)).quantize(Decimal("0.01"))
        )
        if unit_price < Decimal("0"):
            raise ValidationDomainError(
                "Harga satuan barang pada baris Purchase Order tidak boleh negatif.",
                details={"item_id": item_id, "unit_price": str(unit_price), "line_index": idx},
            )
        normalized_lines.append(
            {
                "item_id": item_id,
                "qty_ordered": qty_ordered,
                "unit_price": unit_price,
                "notes": clean_notes,
            }
        )

    return normalized_lines


def _compute_po_total_amount(lines: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0.00")
    for ln in lines:
        qty = Decimal(ln["qty_ordered"])
        price = Decimal(ln.get("unit_price", Decimal("0.00"))).quantize(Decimal("0.01"))
        total += (qty * price).quantize(Decimal("0.01"))
    return total.quantize(Decimal("0.01"))


def _validate_po_lines_ready_for_approval(
    conn: Connection[dict[str, Any]],
    po_id: int,
    *,
    empty_error_message: str,
) -> list[dict[str, Any]]:
    po_repo.lock_po_lines(conn, po_id)
    lines = po_repo.list_po_lines(conn, po_id)
    if not lines:
        raise ValidationDomainError(
            empty_error_message,
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
                    "sku": ln["item_sku"],
                    "uom_code": ln["uom_code"],
                    "qty_ordered": str(qty_ordered),
                },
            )
    return lines


def _validate_delivery_date(order_date: date, expected_delivery_date: date | None) -> None:
    if expected_delivery_date is not None and expected_delivery_date < order_date:
        raise ValidationDomainError(
            "Estimasi tanggal pengiriman tidak boleh lebih awal dari tanggal pesanan.",
            details={
                "order_date": order_date.isoformat(),
                "expected_delivery_date": expected_delivery_date.isoformat(),
            },
        )


def _serialize_po_snapshot(po_detail: dict[str, Any]) -> dict[str, Any]:
    """Menyusun representasi ringkas PO untuk old_values/new_values di audit_logs."""
    exp_date = po_detail.get("expected_delivery_date")
    return {
        "id": po_detail["id"],
        "po_number": po_detail["po_number"],
        "supplier_id": po_detail["supplier_id"],
        "warehouse_id": po_detail["warehouse_id"],
        "status": po_detail["status"],
        "order_date": po_detail["order_date"].isoformat()
        if isinstance(po_detail["order_date"], date)
        else str(po_detail["order_date"]),
        "expected_delivery_date": exp_date.isoformat()
        if isinstance(exp_date, date)
        else exp_date,
        "revised_from_po_id": po_detail.get("revised_from_po_id"),
        "total_amount": f"{Decimal(po_detail.get('total_amount', 0)):.2f}",
        "rejection_reason": po_detail.get("rejection_reason"),
        "notes": po_detail["notes"],
        "closed_reason": po_detail.get("closed_reason"),
        "lines": [
            {
                "id": ln["id"],
                "item_id": ln["item_id"],
                "item_sku": ln["item_sku"],
                "qty_ordered": f"{Decimal(ln['qty_ordered']):.4f}",
                "unit_price": f"{Decimal(ln.get('unit_price', 0)):.2f}",
                "qty_received": f"{Decimal(ln['qty_received']):.4f}",
                "qty_closed": f"{Decimal(ln.get('qty_closed', 0)):.4f}",
                "line_status": ln.get("line_status", "OPEN"),
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
    overdue_only: bool = False,
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

    clean_status: str | list[str] | None = None
    if status is not None:
        raw_tokens = [s.strip().upper() for s in status.split(",") if s.strip()]
        if not raw_tokens:
            clean_status = None
        else:
            for s in raw_tokens:
                if s not in ALLOWED_PO_STATUSES:
                    raise ValidationDomainError(
                        f"Filter status PO '{s}' tidak valid.",
                        details={
                            "status": status,
                            "allowed_values": sorted(ALLOWED_PO_STATUSES),
                        },
                    )
            clean_status = list(dict.fromkeys(raw_tokens))
            if len(clean_status) == 1:
                clean_status = clean_status[0]

    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValidationDomainError(
            "Parameter date_from tidak boleh lebih besar dari date_to.",
            details={
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            },
        )

    # PRD 3.2 poin 2: selain Super Admin & Auditor, PO hanya terlihat pada gudang yang ditugaskan
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
        overdue_only=overdue_only,
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
    access_service.ensure_warehouse_read_access(conn, actor, int(po["warehouse_id"]))
    return po


def create_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    supplier_id: int,
    warehouse_id: int,
    order_date: date,
    expected_delivery_date: date | None = None,
    notes: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    clean_notes = notes.strip() if notes is not None and notes.strip() else None
    _validate_delivery_date(order_date, expected_delivery_date)

    with conn.transaction():
        # PRD 3.2 poin 1: po:create bertanda (g) terhadap warehouse_id PO
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)
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
            expected_delivery_date=expected_delivery_date,
            total_amount=_compute_po_total_amount(normalized_lines),
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
    expected_delivery_date: date | None = None,
    expected_delivery_date_provided: bool = False,
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
        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))
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
        if new_warehouse_id != int(locked["warehouse_id"]):
            access_service.ensure_warehouse_access(conn, actor, new_warehouse_id)
        _validate_supplier_and_warehouse(
            conn, supplier_id=new_supplier_id, warehouse_id=new_warehouse_id
        )

        new_order_date = (
            order_date if order_date is not None else locked["order_date"]
        )
        new_expected_delivery_date = (
            expected_delivery_date
            if expected_delivery_date_provided
            else locked.get("expected_delivery_date")
        )
        _validate_delivery_date(new_order_date, new_expected_delivery_date)
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
            expected_delivery_date=new_expected_delivery_date,
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


def submit_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    notes: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Mengajukan Purchase Order untuk persetujuan berjenjang (DRAFT -> WAITING_L1_APPROVAL)."""
    clean_notes = clean_optional_str(notes)
    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )
        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))
        if locked["status"] != POStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Purchase Order berstatus '{locked['status']}' tidak dapat diajukan persetujuan (harus berstatus DRAFT).",
                details={
                    "po_id": po_id,
                    "current_status": locked["status"],
                    "target_status": POStatus.WAITING_L1_APPROVAL.value,
                },
            )

        _validate_supplier_and_warehouse(
            conn,
            supplier_id=int(locked["supplier_id"]),
            warehouse_id=int(locked["warehouse_id"]),
        )
        _validate_po_lines_ready_for_approval(
            conn,
            po_id,
            empty_error_message="Purchase Order tidak dapat diajukan karena belum memiliki baris barang.",
        )

        po_repo.update_po_submitted(conn, po_id, submitted_by=int(actor["id"]))
        approval_repo.insert_approval_log(
            conn,
            doc_type="PO",
            doc_id=po_id,
            approval_level=0,
            action="SUBMITTED",
            actor_id=int(actor["id"]),
            actor_name=str(actor["full_name"]),
            actor_role=str(actor["role_name"]),
            notes=clean_notes,
        )
        updated = po_repo.get_po_by_id(conn, po_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_SUBMITTED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values={"status": POStatus.DRAFT.value},
            new_values={
                "status": POStatus.WAITING_L1_APPROVAL.value,
                "submitted_by": updated["submitted_by"],
                "total_amount": f"{Decimal(updated.get('total_amount', 0)):.2f}",
            },
            ip_address=ip_address,
        )
        return updated


def approve_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    notes: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Menyetujui PO secara berjenjang (L1 -> ISSUED atau WAITING_L2_APPROVAL -> ISSUED) beserta SoD guard."""
    clean_notes = clean_optional_str(notes)
    actor_perms: set[str] = set(actor.get("permissions", []))

    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )
        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))

        current_status = str(locked["status"])
        if current_status == POStatus.WAITING_L1_APPROVAL.value:
            if PO_APPROVE_L1 not in actor_perms:
                raise PermissionDenied(
                    f"Anda tidak memiliki izin '{PO_APPROVE_L1}' untuk menyetujui Purchase Order Level 1.",
                    details={"required_permission": PO_APPROVE_L1},
                )
            is_sod_override = check_sod_actor(
                actor,
                [locked.get("created_by"), locked.get("submitted_by")],
                action_label="menyetujui Purchase Order Level 1 yang dibuat atau diajukan sendiri",
            )
            _validate_supplier_and_warehouse(
                conn,
                supplier_id=int(locked["supplier_id"]),
                warehouse_id=int(locked["warehouse_id"]),
            )
            _validate_po_lines_ready_for_approval(
                conn,
                po_id,
                empty_error_message="Purchase Order tidak dapat disetujui karena belum memiliki baris barang.",
            )

            threshold = settings_service.get_po_l2_threshold(conn)
            total_amount = Decimal(locked.get("total_amount") or 0).quantize(Decimal("0.01"))
            needs_l2 = total_amount > threshold
            next_status = (
                POStatus.WAITING_L2_APPROVAL.value
                if needs_l2
                else POStatus.ISSUED.value
            )

            po_repo.update_po_l1_approved(
                conn,
                po_id,
                approved_by=int(actor["id"]),
                next_status=next_status,
            )
            approval_repo.insert_approval_log(
                conn,
                doc_type="PO",
                doc_id=po_id,
                approval_level=1,
                action="APPROVED",
                actor_id=int(actor["id"]),
                actor_name=str(actor["full_name"]),
                actor_role=str(actor["role_name"]),
                notes=clean_notes,
            )
            updated = po_repo.get_po_by_id(conn, po_id)
            assert updated is not None

            audit_service.record(
                conn,
                user_id=int(actor["id"]),
                action="PO_APPROVED_L1",
                entity_type="purchase_orders",
                entity_id=po_id,
                old_values={"status": current_status},
                new_values={
                    "status": next_status,
                    "l1_approved_by": updated["l1_approved_by"],
                    "total_amount": f"{total_amount:.2f}",
                    "threshold": f"{threshold:.2f}",
                },
                details={"sod_override": True} if is_sod_override else None,
                ip_address=ip_address,
            )
            return updated

        if current_status == POStatus.WAITING_L2_APPROVAL.value:
            if PO_APPROVE_L2 not in actor_perms:
                raise PermissionDenied(
                    f"Anda tidak memiliki izin '{PO_APPROVE_L2}' untuk menyetujui Purchase Order Level 2.",
                    details={"required_permission": PO_APPROVE_L2},
                )
            is_sod_override = check_sod_actor(
                actor,
                [
                    locked.get("created_by"),
                    locked.get("submitted_by"),
                    locked.get("l1_approved_by"),
                ],
                action_label="menyetujui Purchase Order Level 2 atas dokumen yang dibuat, diajukan, atau disetujui Level 1 oleh dirinya sendiri",
            )
            _validate_supplier_and_warehouse(
                conn,
                supplier_id=int(locked["supplier_id"]),
                warehouse_id=int(locked["warehouse_id"]),
            )
            _validate_po_lines_ready_for_approval(
                conn,
                po_id,
                empty_error_message="Purchase Order tidak dapat disetujui karena belum memiliki baris barang.",
            )

            po_repo.update_po_l2_approved(conn, po_id, approved_by=int(actor["id"]))
            approval_repo.insert_approval_log(
                conn,
                doc_type="PO",
                doc_id=po_id,
                approval_level=2,
                action="APPROVED",
                actor_id=int(actor["id"]),
                actor_name=str(actor["full_name"]),
                actor_role=str(actor["role_name"]),
                notes=clean_notes,
            )
            updated = po_repo.get_po_by_id(conn, po_id)
            assert updated is not None

            audit_service.record(
                conn,
                user_id=int(actor["id"]),
                action="PO_APPROVED_L2",
                entity_type="purchase_orders",
                entity_id=po_id,
                old_values={"status": current_status},
                new_values={
                    "status": POStatus.ISSUED.value,
                    "l2_approved_by": updated["l2_approved_by"],
                    "issued_by": updated["issued_by"],
                },
                details={"sod_override": True} if is_sod_override else None,
                ip_address=ip_address,
            )
            return updated

        raise InvalidStateTransition(
            f"Purchase Order berstatus '{current_status}' tidak dapat disetujui (harus WAITING_L1_APPROVAL atau WAITING_L2_APPROVAL).",
            details={"po_id": po_id, "current_status": current_status},
        )


def reject_purchase_order(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    rejection_reason: str,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Menolak PO yang menunggu persetujuan L1/L2 dan mengembalikannya ke status DRAFT dengan alasan wajib."""
    reason = rejection_reason.strip()
    if not reason:
        raise ValidationDomainError(
            "Alasan penolakan Purchase Order wajib diisi.",
            details={"field": "rejection_reason"},
        )

    actor_perms: set[str] = set(actor.get("permissions", []))
    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )
        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))

        current_status = str(locked["status"])
        if current_status == POStatus.WAITING_L1_APPROVAL.value:
            if PO_APPROVE_L1 not in actor_perms:
                raise PermissionDenied(
                    f"Anda tidak memiliki izin '{PO_APPROVE_L1}' untuk menolak Purchase Order Level 1.",
                    details={"required_permission": PO_APPROVE_L1},
                )
            approval_level = 1
        elif current_status == POStatus.WAITING_L2_APPROVAL.value:
            if PO_APPROVE_L2 not in actor_perms:
                raise PermissionDenied(
                    f"Anda tidak memiliki izin '{PO_APPROVE_L2}' untuk menolak Purchase Order Level 2.",
                    details={"required_permission": PO_APPROVE_L2},
                )
            approval_level = 2
        else:
            raise InvalidStateTransition(
                f"Purchase Order berstatus '{current_status}' tidak dapat ditolak.",
                details={"po_id": po_id, "current_status": current_status},
            )

        po_repo.update_po_rejected(conn, po_id, rejection_reason=reason)
        approval_repo.insert_approval_log(
            conn,
            doc_type="PO",
            doc_id=po_id,
            approval_level=approval_level,
            action="REJECTED",
            actor_id=int(actor["id"]),
            actor_name=str(actor["full_name"]),
            actor_role=str(actor["role_name"]),
            notes=reason,
        )
        updated = po_repo.get_po_by_id(conn, po_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_REJECTED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values={"status": current_status},
            new_values={
                "status": POStatus.DRAFT.value,
                "rejection_reason": reason,
            },
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
    """Transisi langsung DRAFT -> ISSUED untuk PO <= ambang L2 (memerlukan po:approve_l1 dan mematuhi SoD Tahap 38)."""
    actor_perms: set[str] = set(actor.get("permissions", []))
    if PO_APPROVE_L1 not in actor_perms:
        raise PermissionDenied(
            f"Anda tidak memiliki izin '{PO_APPROVE_L1}' untuk menerbitkan Purchase Order secara langsung.",
            details={"required_permission": PO_APPROVE_L1},
        )

    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )
        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))
        if locked["status"] != POStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Purchase Order berstatus '{locked['status']}' tidak dapat diterbitkan (harus berstatus DRAFT).",
                details={
                    "po_id": po_id,
                    "current_status": locked["status"],
                    "target_status": POStatus.ISSUED.value,
                },
            )

        is_sod_override = check_sod_actor(
            actor,
            [locked.get("created_by"), locked.get("submitted_by")],
            action_label="menerbitkan Purchase Order yang dibuat sendiri",
        )

        threshold = settings_service.get_po_l2_threshold(conn)
        total_amount = Decimal(locked.get("total_amount") or 0).quantize(Decimal("0.01"))
        if total_amount > threshold:
            raise InvalidStateTransition(
                f"Total PO Rp {total_amount:,.2f} melebihi ambang persetujuan Level 2 (Rp {threshold:,.2f}); wajib diajukan melalui alur persetujuan berjenjang (/submit -> /approve).",
                details={
                    "po_id": po_id,
                    "total_amount": f"{total_amount:.2f}",
                    "threshold": f"{threshold:.2f}",
                },
            )

        _validate_supplier_and_warehouse(
            conn,
            supplier_id=int(locked["supplier_id"]),
            warehouse_id=int(locked["warehouse_id"]),
        )
        _validate_po_lines_ready_for_approval(
            conn,
            po_id,
            empty_error_message="Purchase Order tidak dapat diterbitkan karena belum memiliki baris barang.",
        )

        po_repo.update_po_issued(conn, po_id, issued_by=int(actor["id"]))
        approval_repo.insert_approval_log(
            conn,
            doc_type="PO",
            doc_id=po_id,
            approval_level=1,
            action="APPROVED",
            actor_id=int(actor["id"]),
            actor_name=str(actor["full_name"]),
            actor_role=str(actor["role_name"]),
            notes="Penerbitan langsung (di bawah ambang approval L2)",
        )
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
            details={"sod_override": True} if is_sod_override else None,
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
        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))

        current_status = str(locked["status"])
        actor_perms: set[str] = set(actor.get("permissions", []))

        if current_status == POStatus.DRAFT.value:
            if PO_CREATE not in actor_perms:
                raise PermissionDenied(
                    f"Anda tidak memiliki izin '{PO_CREATE}' untuk membatalkan PO berstatus DRAFT.",
                    details={"required_permission": PO_CREATE},
                )
        elif current_status in {
            POStatus.WAITING_L1_APPROVAL.value,
            POStatus.WAITING_L2_APPROVAL.value,
        }:
            if PO_CREATE not in actor_perms and PO_CANCEL not in actor_perms:
                raise PermissionDenied(
                    f"Anda tidak memiliki izin '{PO_CREATE}' atau '{PO_CANCEL}' untuk membatalkan PO berstatus {current_status}.",
                    details={"required_permissions": [PO_CREATE, PO_CANCEL]},
                )
        elif current_status == POStatus.ISSUED.value:
            if PO_CANCEL not in actor_perms:
                raise PermissionDenied(
                    f"Anda tidak memiliki izin '{PO_CANCEL}' untuk membatalkan PO berstatus ISSUED.",
                    details={"required_permission": PO_CANCEL},
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

        from app.services import gr_service

        gr_summary = gr_service.gr_status_summary(conn, po_id)
        if gr_summary["draft_count"] > 0 or gr_summary["posted_count"] > 0:
            raise InvalidStateTransition(
                f"Purchase Order berstatus {current_status} tidak dapat dibatalkan karena sudah memiliki Goods Receipt berstatus DRAFT atau POSTED.",
                details={"po_id": po_id, "current_status": current_status, "gr_summary": gr_summary},
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
        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))

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

        from app.services import gr_service

        gr_summary = gr_service.gr_status_summary(conn, po_id)
        if gr_summary["draft_count"] > 0:
            raise InvalidStateTransition(
                "Purchase Order tidak dapat ditutup karena masih memiliki Goods Receipt berstatus DRAFT.",
                details={"po_id": po_id, "current_status": current_status, "gr_summary": gr_summary},
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


def revise_issued_po_as_draft(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Membatalkan PO berstatus ISSUED (belum ada GR) dan menyalin isinya ke PO DRAFT baru (Tahap 36)."""
    actor_perms: set[str] = set(actor.get("permissions", []))
    if PO_CREATE not in actor_perms or PO_CANCEL not in actor_perms:
        raise PermissionDenied(
            f"Diperlukan izin '{PO_CREATE}' dan '{PO_CANCEL}' untuk membatalkan serta menyalin PO ISSUED ke draft baru.",
            details={"required_permissions": [PO_CREATE, PO_CANCEL]},
        )

    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )
        warehouse_id = int(locked["warehouse_id"])
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        if str(locked["status"]) != POStatus.ISSUED.value:
            raise InvalidStateTransition(
                f"Hanya Purchase Order berstatus ISSUED yang dapat dibatalkan dan disalin ke draft (status saat ini: {locked['status']}).",
                details={"po_id": po_id, "current_status": locked["status"]},
            )

        from app.services import gr_service

        gr_summary = gr_service.gr_status_summary(conn, po_id)
        if gr_summary["draft_count"] > 0 or gr_summary["posted_count"] > 0:
            raise InvalidStateTransition(
                "Purchase Order sudah memiliki Goods Receipt sehingga tidak dapat disalin ulang ke draft. Gunakan fitur Short-Close untuk menyesuaikan sisa pesanan.",
                details={"po_id": po_id, "gr_summary": gr_summary},
            )

        _validate_supplier_and_warehouse(
            conn,
            supplier_id=int(locked["supplier_id"]),
            warehouse_id=warehouse_id,
        )
        old_lines = po_repo.lock_po_lines(conn, po_id)

        po_repo.update_po_cancelled(conn, po_id)
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_CANCELLED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values={"status": POStatus.ISSUED.value},
            new_values={"status": POStatus.CANCELLED.value, "revised_to_new_draft": True},
            ip_address=ip_address,
        )

        ref_date = locked["order_date"] if isinstance(locked["order_date"], date) else date.today()
        new_po_number = numbering_service.generate_document_number(
            conn, DocType.PO, reference_date=ref_date
        )
        cloned_lines = [
            {
                "item_id": int(ln["item_id"]),
                "qty_ordered": Decimal(ln["qty_ordered"]),
                "unit_price": Decimal(ln.get("unit_price", Decimal("0.00"))).quantize(Decimal("0.01")),
                "notes": ln.get("notes"),
            }
            for ln in old_lines
        ]
        new_header = po_repo.insert_po_header(
            conn,
            po_number=new_po_number,
            supplier_id=int(locked["supplier_id"]),
            warehouse_id=warehouse_id,
            order_date=ref_date,
            expected_delivery_date=locked.get("expected_delivery_date"),
            revised_from_po_id=po_id,
            total_amount=_compute_po_total_amount(cloned_lines),
            notes=locked.get("notes"),
            created_by=int(actor["id"]),
        )
        new_po_id = int(new_header["id"])

        if cloned_lines:
            po_repo.replace_po_lines(
                conn,
                po_id=new_po_id,
                lines=cloned_lines,
                actor_id=int(actor["id"]),
            )

        created_draft = po_repo.get_po_by_id(conn, new_po_id)
        assert created_draft is not None
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_REVISED_FROM_ISSUED",
            entity_type="purchase_orders",
            entity_id=new_po_id,
            old_values={"revised_from_po_id": po_id, "revised_from_po_number": locked["po_number"]},
            new_values=_serialize_po_snapshot(created_draft),
            ip_address=ip_address,
        )
        return created_draft


def close_purchase_order_line(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    po_line_id: int,
    closed_reason: str,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Menutup sisa kuantitas satu baris PO (Line-level Short-Close, Tahap 36)."""
    clean_reason = closed_reason.strip() if closed_reason else ""
    if not clean_reason:
        raise ValidationDomainError(
            "Alasan penutupan baris PO (closed_reason) wajib diisi.",
            details={"field": "closed_reason"},
        )

    with conn.transaction():
        locked = po_repo.lock_po_by_id(conn, po_id)
        if not locked:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )
        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))

        current_status = str(locked["status"])
        if current_status not in (
            POStatus.ISSUED.value,
            POStatus.PARTIALLY_RECEIVED.value,
        ):
            raise InvalidStateTransition(
                f"Baris PO berstatus '{current_status}' tidak dapat ditutup sebagian (PO harus ISSUED atau PARTIALLY_RECEIVED).",
                details={"po_id": po_id, "current_status": current_status},
            )

        from app.services import gr_service

        gr_summary = gr_service.gr_status_summary(conn, po_id)
        if gr_summary["draft_count"] > 0:
            raise InvalidStateTransition(
                "Baris PO tidak dapat ditutup karena masih ada Goods Receipt berstatus DRAFT untuk PO ini.",
                details={"po_id": po_id, "gr_summary": gr_summary},
            )

        lines = po_repo.lock_po_lines(conn, po_id)
        target_line = next((ln for ln in lines if int(ln["id"]) == po_line_id), None)
        if not target_line:
            raise NotFoundError(
                "Baris Purchase Order tidak ditemukan.",
                details={"po_id": po_id, "po_line_id": po_line_id},
            )

        qty_ordered = Decimal(target_line["qty_ordered"]).quantize(FOUR_PLACES)
        qty_received = Decimal(target_line["qty_received"]).quantize(FOUR_PLACES)
        qty_closed_existing = Decimal(target_line.get("qty_closed", 0)).quantize(FOUR_PLACES)
        remaining = (qty_ordered - qty_received - qty_closed_existing).quantize(FOUR_PLACES)

        if str(target_line.get("line_status")) in ("RECEIVED", "CLOSED") or remaining <= Decimal("0.0000"):
            raise InvalidStateTransition(
                "Baris PO ini sudah diterima seluruhnya atau sudah ditutup sebelumnya.",
                details={"po_id": po_id, "po_line_id": po_line_id, "remaining": str(remaining)},
            )

        new_qty_closed = (qty_ordered - qty_received).quantize(FOUR_PLACES)
        po_repo.close_po_line(
            conn,
            po_line_id=po_line_id,
            qty_closed=new_qty_closed,
            closed_reason=clean_reason,
            closed_by=int(actor["id"]),
        )

        refreshed_lines = po_repo.list_po_lines(conn, po_id)
        all_settled = all(
            (Decimal(ln["qty_received"]) + Decimal(ln["qty_closed"])).quantize(FOUR_PLACES)
            >= Decimal(ln["qty_ordered"]).quantize(FOUR_PLACES)
            for ln in refreshed_lines
        )
        if all_settled:
            has_any_closed = any(
                Decimal(ln["qty_closed"]).quantize(FOUR_PLACES) > Decimal("0.0000")
                for ln in refreshed_lines
            )
            if has_any_closed:
                po_repo.update_po_closed(
                    conn,
                    po_id,
                    closed_reason=f"Seluruh baris PO selesai/ditutup (Short-Close). Terakhir: {clean_reason}",
                    closed_by=int(actor["id"]),
                )
            else:
                po_repo.update_po_status(conn, po_id, status=POStatus.RECEIVED.value)

        updated = po_repo.get_po_by_id(conn, po_id)
        assert updated is not None
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_LINE_CLOSED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values={
                "po_line_id": po_line_id,
                "status": current_status,
                "line_status": target_line.get("line_status"),
                "qty_closed": f"{qty_closed_existing:.4f}",
            },
            new_values={
                "po_line_id": po_line_id,
                "status": updated["status"],
                "line_status": "CLOSED",
                "qty_closed": f"{new_qty_closed:.4f}",
                "line_closed_reason": clean_reason,
            },
            ip_address=ip_address,
        )
        return updated


def apply_receipt(
    conn: Connection[dict[str, Any]],
    *,
    po_id: int,
    old_po_status: str,
    added_per_po_line: dict[int, Decimal],
    gr_id: int,
    gr_number: str,
    actor_id: int,
    ip_address: str | None = None,
) -> str:
    """Contract PUR (`apply_receipt`): memperbarui `qty_received` baris PO dan status fulfillment PO (`PARTIALLY_RECEIVED` / `RECEIVED` / `CLOSED`) dalam transaksi posting GR (PRD 4.3, 6.7)."""
    for po_line_id in sorted(added_per_po_line.keys()):
        po_repo.add_po_line_received_qty(
            conn,
            po_line_id=po_line_id,
            qty_added=added_per_po_line[po_line_id],
        )

    updated_po_lines = po_repo.list_po_lines(conn, po_id)
    all_received_full = all(
        Decimal(ln["qty_received"]).quantize(FOUR_PLACES)
        >= Decimal(ln["qty_ordered"]).quantize(FOUR_PLACES)
        for ln in updated_po_lines
    )
    all_settled = all(
        (Decimal(ln["qty_received"]) + Decimal(ln["qty_closed"])).quantize(FOUR_PLACES)
        >= Decimal(ln["qty_ordered"]).quantize(FOUR_PLACES)
        for ln in updated_po_lines
    )
    if all_received_full:
        new_po_status = POStatus.RECEIVED.value
        if new_po_status != old_po_status:
            po_repo.update_po_status(conn, po_id, status=new_po_status)
    elif all_settled:
        new_po_status = POStatus.CLOSED.value
        if new_po_status != old_po_status:
            po_repo.update_po_closed(
                conn,
                po_id,
                closed_reason="Seluruh baris PO selesai diterima atau ditutup sebagian (Short-Close).",
                closed_by=actor_id,
            )
    else:
        new_po_status = POStatus.PARTIALLY_RECEIVED.value
        if new_po_status != old_po_status:
            po_repo.update_po_status(conn, po_id, status=new_po_status)

    audit_service.record(
        conn,
        user_id=actor_id,
        action="PO_RECEIPT_PROGRESS_UPDATED",
        entity_type="purchase_orders",
        entity_id=po_id,
        old_values={"status": old_po_status},
        new_values={
            "status": new_po_status,
            "gr_id": gr_id,
            "gr_number": gr_number,
        },
        ip_address=ip_address,
    )
    return new_po_status

