"""Service logika bisnis Goods Receipt (GR) dan posting atomik penerimaan barang dari PO (FR-05, PRD 5.1, 6.2, 6.5, AC-01, AC-07, AC-13)."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import Connection

from app.core.exceptions import (
    InactiveReferenceError,
    InvalidLocationError,
    InvalidStateTransition,
    NotFoundError,
    OverReceipt,
    ValidationDomainError,
)
from app.core.permissions import ROLE_WAREHOUSE_STAFF
from app.repositories import gr_repo, inventory_repo, po_repo, warehouse_repo
from app.services import (
    access_service,
    audit_service,
    inventory_service,
    numbering_service,
)
from app.utils.enums import DocType, GRStatus, MovementType, POStatus, ReferenceType
from app.utils.pagination import build_order_by, normalize_pagination

FOUR_PLACES = Decimal("0.0001")

GR_SORT_COLUMNS: dict[str, str] = {
    "id": "gr.id",
    "gr_number": "gr.gr_number",
    "received_date": "gr.received_date",
    "status": "gr.status",
    "created_at": "gr.created_at",
}

ALLOWED_GR_STATUSES: frozenset[str] = frozenset(s.value for s in GRStatus)
RECEIVABLE_PO_STATUSES: frozenset[str] = frozenset(
    {POStatus.ISSUED.value, POStatus.PARTIALLY_RECEIVED.value}
)


def _normalize_positive_qty(value: Decimal, *, field_name: str = "qty_received") -> Decimal:
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


def _validate_and_normalize_gr_lines(
    conn: Connection[dict[str, Any]],
    *,
    po_id: int,
    warehouse_id: int,
    po_lines_by_id: dict[int, dict[str, Any]],
    lines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Memvalidasi daftar baris GR terhadap baris PO, lokasi gudang tujuan, UoM, dan batas over-receipt."""
    seen_pairs: set[tuple[int, int]] = set()
    requested_per_po_line: dict[int, Decimal] = defaultdict(lambda: Decimal("0.0000"))
    normalized_lines: list[dict[str, Any]] = []

    for idx, line in enumerate(lines):
        po_line_id = int(line["po_line_id"])
        location_id = int(line["location_id"])

        if po_line_id not in po_lines_by_id:
            raise ValidationDomainError(
                "Baris PO (po_line_id) tidak ditemukan pada Purchase Order ini.",
                details={
                    "po_id": po_id,
                    "po_line_id": po_line_id,
                    "line_index": idx,
                },
            )

        pair = (po_line_id, location_id)
        if pair in seen_pairs:
            raise ValidationDomainError(
                "Kombinasi po_line_id dan location_id tidak boleh duplikat dalam satu Goods Receipt.",
                details={
                    "po_line_id": po_line_id,
                    "location_id": location_id,
                    "line_index": idx,
                },
            )
        seen_pairs.add(pair)

        qty_received = _normalize_positive_qty(
            line["qty_received"], field_name="qty_received"
        )

        po_line = po_lines_by_id[po_line_id]
        item = inventory_repo.get_item_with_uom(conn, int(po_line["item_id"]))
        if not item:
            raise NotFoundError(
                "Barang pada baris PO tidak ditemukan.",
                details={"item_id": po_line["item_id"], "line_index": idx},
            )
        if not item["is_active"]:
            raise InactiveReferenceError(
                f"Barang '{item['sku']}' berstatus tidak aktif.",
                details={"item_id": item["id"], "sku": item["sku"], "line_index": idx},
            )
        if not bool(item["allow_decimal"]) and qty_received != qty_received.to_integral_value():
            raise ValidationDomainError(
                f"Barang '{item['sku']}' menggunakan UoM '{item['uom_code']}' yang harus berupa bilangan bulat.",
                details={
                    "item_id": item["id"],
                    "sku": item["sku"],
                    "uom_code": item["uom_code"],
                    "qty_received": str(qty_received),
                    "line_index": idx,
                },
            )

        location = warehouse_repo.get_location_by_id(conn, location_id)
        if not location or int(location["warehouse_id"]) != int(warehouse_id):
            raise InvalidLocationError(
                "Lokasi penyimpanan tidak ditemukan atau bukan milik gudang tujuan PO.",
                details={
                    "warehouse_id": warehouse_id,
                    "location_id": location_id,
                    "line_index": idx,
                },
            )
        if not location["is_active"]:
            raise InvalidLocationError(
                f"Lokasi penyimpanan '{location['code']}' berstatus tidak aktif.",
                details={
                    "warehouse_id": warehouse_id,
                    "location_id": location_id,
                    "location_code": location["code"],
                    "line_index": idx,
                },
            )

        requested_per_po_line[po_line_id] = (
            requested_per_po_line[po_line_id] + qty_received
        ).quantize(FOUR_PLACES)

        clean_notes = (
            line["notes"].strip()
            if line.get("notes") is not None and str(line["notes"]).strip()
            else None
        )
        normalized_lines.append(
            {
                "po_line_id": po_line_id,
                "location_id": location_id,
                "qty_received": qty_received,
                "notes": clean_notes,
            }
        )

    # Pemeriksaan over-receipt: qty_received_current_gr + po_line.qty_received <= po_line.qty_ordered (PRD 6.2)
    for po_line_id, total_current_gr in requested_per_po_line.items():
        po_line = po_lines_by_id[po_line_id]
        already_received = Decimal(po_line["qty_received"]).quantize(FOUR_PLACES)
        qty_ordered = Decimal(po_line["qty_ordered"]).quantize(FOUR_PLACES)
        remaining = (qty_ordered - already_received).quantize(FOUR_PLACES)

        if total_current_gr + already_received > qty_ordered:
            raise OverReceipt(
                f"Kuantitas penerimaan ({total_current_gr:.4f}) melebihi sisa pesanan PO ({remaining:.4f}).",
                details={
                    "po_id": po_id,
                    "po_line_id": po_line_id,
                    "item_id": po_line["item_id"],
                    "qty_ordered": f"{qty_ordered:.4f}",
                    "qty_already_received": f"{already_received:.4f}",
                    "qty_remaining": f"{remaining:.4f}",
                    "qty_requested": f"{total_current_gr:.4f}",
                },
            )

    return normalized_lines


def _serialize_gr_snapshot(gr_detail: dict[str, Any]) -> dict[str, Any]:
    """Menyusun representasi ringkas GR untuk old_values/new_values di audit_logs."""
    return {
        "id": gr_detail["id"],
        "gr_number": gr_detail["gr_number"],
        "po_id": gr_detail["po_id"],
        "po_number": gr_detail["po_number"],
        "warehouse_id": gr_detail["warehouse_id"],
        "status": gr_detail["status"],
        "received_date": gr_detail["received_date"].isoformat()
        if isinstance(gr_detail["received_date"], date)
        else str(gr_detail["received_date"]),
        "notes": gr_detail["notes"],
        "lines": [
            {
                "id": ln["id"],
                "po_line_id": ln["po_line_id"],
                "item_id": ln["item_id"],
                "item_sku": ln["item_sku"],
                "location_id": ln["location_id"],
                "location_code": ln["location_code"],
                "qty_received": f"{Decimal(ln['qty_received']):.4f}",
                "notes": ln.get("notes"),
            }
            for ln in gr_detail.get("lines", [])
        ],
    }


def list_goods_receipts(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    warehouse_id: int | None = None,
    po_id: int | None = None,
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
        allowed_columns=GR_SORT_COLUMNS,
        default_column="id",
        default_dir="DESC",
    )

    clean_status: str | None = None
    if status is not None:
        clean_status = status.strip().upper()
        if clean_status not in ALLOWED_GR_STATUSES:
            raise ValidationDomainError(
                f"Filter status GR '{status}' tidak valid.",
                details={
                    "status": status,
                    "allowed_values": sorted(ALLOWED_GR_STATUSES),
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

    # PRD 3.1 & 3.2 poin 5: Warehouse Staff hanya melihat GR pada gudang yang ditugaskan
    scoped_ids = access_service.get_scoped_warehouse_ids_for_read(conn, actor)
    if scoped_ids is not None and warehouse_id is not None:
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

    items, total = gr_repo.list_goods_receipts(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        scoped_warehouse_ids=scoped_ids,
        warehouse_id=warehouse_id,
        po_id=po_id,
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


def get_goods_receipt(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    gr_id: int,
) -> dict[str, Any]:
    gr = gr_repo.get_gr_by_id(conn, gr_id)
    if not gr:
        raise NotFoundError(
            "Goods Receipt tidak ditemukan.",
            details={"gr_id": gr_id},
        )
    if actor.get("role_name") == ROLE_WAREHOUSE_STAFF:
        access_service.ensure_warehouse_access(conn, actor, int(gr["warehouse_id"]))
    return gr


def create_goods_receipt(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    po_id: int,
    received_date: date,
    notes: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Membuat dokumen Goods Receipt berstatus DRAFT terhadap PO berstatus ISSUED / PARTIALLY_RECEIVED (FR-05)."""
    clean_notes = notes.strip() if notes is not None and notes.strip() else None

    with conn.transaction():
        po = po_repo.get_po_by_id(conn, po_id)
        if not po:
            raise NotFoundError(
                "Purchase Order tidak ditemukan.",
                details={"po_id": po_id},
            )

        warehouse_id = int(po["warehouse_id"])
        # PRD 3.2 poin 4: Pada GR, gudang tujuan (gudang yang tercantum pada PO) harus termasuk gudang yang ditugaskan
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        if po["status"] not in RECEIVABLE_PO_STATUSES:
            raise InvalidStateTransition(
                f"Goods Receipt hanya dapat dibuat untuk PO berstatus ISSUED atau PARTIALLY_RECEIVED (status PO saat ini: '{po['status']}').",
                details={"po_id": po_id, "po_status": po["status"]},
            )

        if not po["warehouse_is_active"]:
            raise InactiveReferenceError(
                "Gudang tujuan pada Purchase Order berstatus tidak aktif.",
                details={"warehouse_id": warehouse_id},
            )

        po_lines_by_id = {int(ln["id"]): ln for ln in po["lines"]}
        normalized_lines = _validate_and_normalize_gr_lines(
            conn,
            po_id=po_id,
            warehouse_id=warehouse_id,
            po_lines_by_id=po_lines_by_id,
            lines=lines or [],
        )

        gr_number = numbering_service.generate_document_number(
            conn, DocType.GR, reference_date=received_date
        )
        header = gr_repo.insert_gr_header(
            conn,
            gr_number=gr_number,
            po_id=po_id,
            warehouse_id=warehouse_id,
            received_date=received_date,
            notes=clean_notes,
            created_by=int(actor["id"]),
        )
        gr_id = int(header["id"])

        if normalized_lines:
            gr_repo.replace_gr_lines(
                conn,
                gr_id=gr_id,
                po_id=po_id,
                warehouse_id=warehouse_id,
                lines=normalized_lines,
                actor_id=int(actor["id"]),
            )

        created = gr_repo.get_gr_by_id(conn, gr_id)
        assert created is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="GR_CREATED",
            entity_type="goods_receipts",
            entity_id=gr_id,
            old_values=None,
            new_values=_serialize_gr_snapshot(created),
            ip_address=ip_address,
        )
        return created


def update_goods_receipt(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    gr_id: int,
    received_date: date | None = None,
    notes: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Memperbarui dokumen Goods Receipt yang masih berstatus DRAFT."""
    with conn.transaction():
        locked = gr_repo.lock_gr_by_id(conn, gr_id)
        if not locked:
            raise NotFoundError(
                "Goods Receipt tidak ditemukan.",
                details={"gr_id": gr_id},
            )

        warehouse_id = int(locked["warehouse_id"])
        po_id = int(locked["po_id"])
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        if locked["status"] != GRStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Goods Receipt berstatus '{locked['status']}' tidak dapat diubah; hanya GR berstatus DRAFT yang dapat direvisi.",
                details={"gr_id": gr_id, "current_status": locked["status"]},
            )

        before_detail = gr_repo.get_gr_by_id(conn, gr_id)
        assert before_detail is not None
        old_snapshot = _serialize_gr_snapshot(before_detail)

        po = po_repo.get_po_by_id(conn, po_id)
        assert po is not None
        if po["status"] not in RECEIVABLE_PO_STATUSES:
            raise InvalidStateTransition(
                f"Purchase Order terkait berstatus '{po['status']}' sehingga GR tidak dapat diubah.",
                details={"gr_id": gr_id, "po_id": po_id, "po_status": po["status"]},
            )

        new_received_date = (
            received_date if received_date is not None else locked["received_date"]
        )
        new_notes = (
            (notes.strip() if notes.strip() else None)
            if notes is not None
            else locked["notes"]
        )

        gr_repo.update_gr_draft_header(
            conn,
            gr_id,
            received_date=new_received_date,
            notes=new_notes,
        )

        if lines is not None:
            po_lines_by_id = {int(ln["id"]): ln for ln in po["lines"]}
            normalized_lines = _validate_and_normalize_gr_lines(
                conn,
                po_id=po_id,
                warehouse_id=warehouse_id,
                po_lines_by_id=po_lines_by_id,
                lines=lines,
            )
            gr_repo.replace_gr_lines(
                conn,
                gr_id=gr_id,
                po_id=po_id,
                warehouse_id=warehouse_id,
                lines=normalized_lines,
                actor_id=int(actor["id"]),
            )

        updated = gr_repo.get_gr_by_id(conn, gr_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="GR_UPDATED",
            entity_type="goods_receipts",
            entity_id=gr_id,
            old_values=old_snapshot,
            new_values=_serialize_gr_snapshot(updated),
            ip_address=ip_address,
        )
        return updated


def post_goods_receipt(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    gr_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Mem-posting Goods Receipt (DRAFT -> POSTED) secara atomik di bawah penguncian baris (FOLDER_STRUCTURE 4.3, AC-01, AC-07, AC-13)."""
    with conn.transaction():
        # 1. Kunci baris header GR (FOR UPDATE) & periksa status harus DRAFT
        gr = gr_repo.lock_gr_by_id(conn, gr_id)
        if not gr:
            raise NotFoundError(
                "Goods Receipt tidak ditemukan.",
                details={"gr_id": gr_id},
            )
        if gr["status"] != GRStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Goods Receipt berstatus '{gr['status']}' tidak dapat diposting (harus berstatus DRAFT).",
                details={
                    "gr_id": gr_id,
                    "current_status": gr["status"],
                    "target_status": GRStatus.POSTED.value,
                },
            )

        warehouse_id = int(gr["warehouse_id"])
        po_id = int(gr["po_id"])

        # 2. Periksa penugasan gudang (AC-12)
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        # 3. Kunci baris header PO terkait (FOR UPDATE) & pastikan status ISSUED / PARTIALLY_RECEIVED
        po = po_repo.lock_po_by_id(conn, po_id)
        assert po is not None
        if po["status"] not in RECEIVABLE_PO_STATUSES:
            raise InvalidStateTransition(
                f"Purchase Order terkait berstatus '{po['status']}' sehingga Goods Receipt tidak dapat diposting.",
                details={"gr_id": gr_id, "po_id": po_id, "po_status": po["status"]},
            )

        # 4. Kunci seluruh baris PO (FOR UPDATE, urut id) & hitung ulang over-receipt secara mengikat
        locked_po_lines = po_repo.lock_po_lines(conn, po_id)
        po_lines_by_id = {int(ln["id"]): ln for ln in locked_po_lines}

        gr_lines = gr_repo.list_gr_lines(conn, gr_id)
        if not gr_lines:
            raise ValidationDomainError(
                "Goods Receipt tidak dapat diposting karena belum memiliki baris penerimaan barang.",
                details={"gr_id": gr_id},
            )

        # Validasi ulang baris GR terhadap baris PO yang sudah dikunci FOR UPDATE
        _validate_and_normalize_gr_lines(
            conn,
            po_id=po_id,
            warehouse_id=warehouse_id,
            po_lines_by_id=po_lines_by_id,
            lines=[
                {
                    "po_line_id": ln["po_line_id"],
                    "location_id": ln["location_id"],
                    "qty_received": Decimal(ln["qty_received"]),
                    "notes": ln.get("notes"),
                }
                for ln in gr_lines
            ],
        )

        # 5. Urutan penguncian seragam (PRD 6.5):
        #    (3) Kunci seluruh lokasi penyimpanan dengan FOR SHARE diurutkan berdasarkan id
        unique_loc_ids = sorted({int(ln["location_id"]) for ln in gr_lines})
        for loc_id in unique_loc_ids:
            inventory_repo.lock_location_for_share(conn, loc_id)

        #    (4) Terapkan mutasi saldo & tulis ledger diurutkan berdasarkan (warehouse_id, location_id, item_id)
        sorted_gr_lines = sorted(
            gr_lines,
            key=lambda ln: (
                int(ln["warehouse_id"]),
                int(ln["location_id"]),
                int(ln["item_id"]),
                int(ln["id"]),
            ),
        )
        added_per_po_line: dict[int, Decimal] = defaultdict(lambda: Decimal("0.0000"))

        for ln in sorted_gr_lines:
            qty_rec = Decimal(ln["qty_received"]).quantize(FOUR_PLACES)
            inventory_service.apply_movement(
                conn,
                movement_type=MovementType.IN_PURCHASE,
                warehouse_id=warehouse_id,
                location_id=int(ln["location_id"]),
                item_id=int(ln["item_id"]),
                qty_change=qty_rec,
                reference_type=ReferenceType.GOODS_RECEIPT,
                reference_id=gr_id,
                created_by=int(actor["id"]),
                notes=ln.get("notes") or f"Penerimaan GR {gr['gr_number']}",
            )
            po_line_id = int(ln["po_line_id"])
            added_per_po_line[po_line_id] = (
                added_per_po_line[po_line_id] + qty_rec
            ).quantize(FOUR_PLACES)

        # 6. Tambahkan qty_received pada baris PO (diurutkan po_line_id)
        for po_line_id in sorted(added_per_po_line.keys()):
            po_repo.add_po_line_received_qty(
                conn,
                po_line_id=po_line_id,
                qty_added=added_per_po_line[po_line_id],
            )

        # 7. Evaluasi ulang status PO (PARTIALLY_RECEIVED vs RECEIVED)
        updated_po_lines = po_repo.list_po_lines(conn, po_id)
        all_fulfilled = all(
            Decimal(ln["qty_received"]).quantize(FOUR_PLACES)
            == Decimal(ln["qty_ordered"]).quantize(FOUR_PLACES)
            for ln in updated_po_lines
        )
        new_po_status = (
            POStatus.RECEIVED.value
            if all_fulfilled
            else POStatus.PARTIALLY_RECEIVED.value
        )
        old_po_status = str(po["status"])
        if new_po_status != old_po_status:
            po_repo.update_po_status(conn, po_id, status=new_po_status)

        # 8. Tandai GR sebagai POSTED
        gr_repo.mark_gr_posted(conn, gr_id, posted_by=int(actor["id"]))

        posted_gr = gr_repo.get_gr_by_id(conn, gr_id)
        assert posted_gr is not None

        # 9. Catat audit log untuk GR dan PO dalam transaksi yang sama
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="GR_POSTED",
            entity_type="goods_receipts",
            entity_id=gr_id,
            old_values={"status": GRStatus.DRAFT.value},
            new_values={
                "status": GRStatus.POSTED.value,
                "posted_by": posted_gr["posted_by"],
                "posted_at": posted_gr["posted_at"].isoformat()
                if posted_gr["posted_at"]
                else None,
                "po_id": po_id,
                "po_status_after": new_po_status,
            },
            ip_address=ip_address,
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="PO_RECEIPT_PROGRESS_UPDATED",
            entity_type="purchase_orders",
            entity_id=po_id,
            old_values={"status": old_po_status},
            new_values={
                "status": new_po_status,
                "gr_id": gr_id,
                "gr_number": posted_gr["gr_number"],
            },
            ip_address=ip_address,
        )
        return posted_gr


def cancel_goods_receipt(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    gr_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Membatalkan Goods Receipt (DRAFT -> CANCELLED, PRD 5.1)."""
    with conn.transaction():
        gr = gr_repo.lock_gr_by_id(conn, gr_id)
        if not gr:
            raise NotFoundError(
                "Goods Receipt tidak ditemukan.",
                details={"gr_id": gr_id},
            )

        access_service.ensure_warehouse_access(conn, actor, int(gr["warehouse_id"]))

        if gr["status"] != GRStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Goods Receipt berstatus '{gr['status']}' tidak dapat dibatalkan (hanya GR berstatus DRAFT yang dapat dibatalkan).",
                details={
                    "gr_id": gr_id,
                    "current_status": gr["status"],
                    "target_status": GRStatus.CANCELLED.value,
                },
            )

        gr_repo.mark_gr_cancelled(conn, gr_id)
        updated = gr_repo.get_gr_by_id(conn, gr_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="GR_CANCELLED",
            entity_type="goods_receipts",
            entity_id=gr_id,
            old_values={"status": GRStatus.DRAFT.value},
            new_values={"status": GRStatus.CANCELLED.value},
            ip_address=ip_address,
        )
        return updated

