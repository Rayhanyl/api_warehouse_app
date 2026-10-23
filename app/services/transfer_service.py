"""Service logika bisnis Stock Transfer: DRAFT -> APPROVED -> SHIPPED -> RECEIVED (FR-06, PRD 5.1, 6.1, 6.3, 6.5, 6.6, 6.7).

AC terkait: AC-02 (stok negatif), AC-03 (konsistensi transfer), AC-06 (konkurensi pengiriman),
AC-09 (selisih penerimaan), AC-12 (warehouse scoping), AC-13 (pencegahan pemrosesan ganda).
"""

from datetime import date
from decimal import Decimal
from typing import Any

from psycopg import Connection

from app.core.exceptions import (
    InactiveReferenceError,
    InvalidLocationError,
    InvalidStateTransition,
    LocationFrozen,
    NotFoundError,
    PermissionDenied,
    TransferQtyExceedsShipped,
    ValidationDomainError,
    WarehouseNotAssigned,
)
from app.core.permissions import TRANSFER_APPROVE, TRANSFER_CREATE
from app.repositories import (
    inventory_repo,
    opname_repo,
    transfer_repo,
    warehouse_repo,
)
from app.services import (
    access_service,
    audit_service,
    inventory_service,
    numbering_service,
)
from app.utils.enums import DocType, MovementType, ReferenceType, TransferStatus
from app.utils.pagination import build_order_by, normalize_pagination

FOUR_PLACES = Decimal("0.0001")
ZERO = Decimal("0.0000")
ENTITY_TYPE = "stock_transfers"

TRANSFER_SORT_COLUMNS: dict[str, str] = {
    "id": "st.id",
    "transfer_number": "st.transfer_number",
    "status": "st.status",
    "created_at": "st.created_at",
    "shipped_at": "st.shipped_at",
    "received_at": "st.received_at",
}

ALLOWED_TRANSFER_STATUSES: frozenset[str] = frozenset(s.value for s in TransferStatus)


# ============================================================================
# Helper validasi
# ============================================================================
def _normalize_qty(value: Any, *, field_name: str, allow_zero: bool) -> Decimal:
    """Memastikan kuantitas Decimal (bukan float), maksimal 4 desimal, dan > 0 (atau >= 0) (PRD 6.9)."""
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

    if not value.is_finite():
        raise ValidationDomainError(
            f"Field '{field_name}' harus berupa angka yang valid.",
            details={"field": field_name, "value": str(value)},
        )
    quantized = value.quantize(FOUR_PLACES)
    if quantized != value:
        raise ValidationDomainError(
            f"Field '{field_name}' maksimal memiliki 4 angka di belakang koma.",
            details={"field": field_name, "value": str(value)},
        )
    if quantized < ZERO or (not allow_zero and quantized == ZERO):
        raise ValidationDomainError(
            f"Field '{field_name}' harus {'>= 0' if allow_zero else 'lebih besar dari 0'}.",
            details={"field": field_name, "value": str(quantized)},
        )
    return quantized


def _ensure_integer_if_required(
    qty: Decimal, *, item: dict[str, Any], field_name: str, extra: dict[str, Any]
) -> None:
    """Kuantitas barang ber-UoM allow_decimal = FALSE wajib bilangan bulat (FR-02, PRD 6.9)."""
    if not bool(item["allow_decimal"]) and qty != qty.to_integral_value():
        raise ValidationDomainError(
            f"Barang '{item['sku']}' menggunakan UoM '{item['uom_code']}' yang harus berupa bilangan bulat.",
            details={
                "item_id": item["id"],
                "sku": item["sku"],
                "uom_code": item["uom_code"],
                field_name: str(qty),
                **extra,
            },
        )


def _validate_warehouse_and_location(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int,
    role: str,
) -> None:
    """Gudang wajib ada & aktif (INACTIVE_REFERENCE); lokasi wajib aktif & milik gudang tsb (INVALID_LOCATION) (PRD 6.3)."""
    warehouse = warehouse_repo.get_warehouse_by_id(conn, warehouse_id)
    if not warehouse:
        raise NotFoundError(
            f"Gudang {role} tidak ditemukan.",
            details={f"{role}_warehouse_id": warehouse_id},
        )
    if not warehouse["is_active"]:
        raise InactiveReferenceError(
            f"Gudang {role} '{warehouse['code']}' berstatus tidak aktif.",
            details={f"{role}_warehouse_id": warehouse_id},
        )

    location = warehouse_repo.get_location_by_id(conn, location_id)
    if not location or int(location["warehouse_id"]) != int(warehouse_id):
        raise InvalidLocationError(
            f"Lokasi {role} tidak ditemukan atau bukan milik gudang {role}.",
            details={
                f"{role}_warehouse_id": warehouse_id,
                f"{role}_location_id": location_id,
            },
        )
    if not location["is_active"]:
        raise InvalidLocationError(
            f"Lokasi {role} '{location['code']}' berstatus tidak aktif.",
            details={
                f"{role}_warehouse_id": warehouse_id,
                f"{role}_location_id": location_id,
            },
        )


def _validate_header(
    conn: Connection[dict[str, Any]],
    *,
    source_warehouse_id: int,
    source_location_id: int,
    destination_warehouse_id: int,
    destination_location_id: int,
) -> None:
    """Validasi header Transfer: asal != tujuan, gudang aktif, lokasi valid & aktif (PRD 5.1, 6.3)."""
    if (int(source_warehouse_id), int(source_location_id)) == (
        int(destination_warehouse_id),
        int(destination_location_id),
    ):
        raise ValidationDomainError(
            "Kombinasi gudang & lokasi asal tidak boleh sama dengan gudang & lokasi tujuan.",
            details={
                "source_warehouse_id": source_warehouse_id,
                "source_location_id": source_location_id,
                "destination_warehouse_id": destination_warehouse_id,
                "destination_location_id": destination_location_id,
            },
        )
    _validate_warehouse_and_location(
        conn,
        warehouse_id=source_warehouse_id,
        location_id=source_location_id,
        role="source",
    )
    _validate_warehouse_and_location(
        conn,
        warehouse_id=destination_warehouse_id,
        location_id=destination_location_id,
        role="destination",
    )


def _validate_and_normalize_lines(
    conn: Connection[dict[str, Any]], lines: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validasi baris Transfer: barang unik per dokumen, aktif, qty > 0, aturan UoM (FR-06, PRD 6.9)."""
    seen_items: set[int] = set()
    normalized: list[dict[str, Any]] = []

    for idx, line in enumerate(lines):
        item_id = int(line["item_id"])
        if item_id in seen_items:
            raise ValidationDomainError(
                "Satu barang hanya boleh muncul satu kali dalam satu Transfer.",
                details={"item_id": item_id, "line_index": idx},
            )
        seen_items.add(item_id)

        qty = _normalize_qty(line["qty"], field_name="qty", allow_zero=False)

        item = inventory_repo.get_item_with_uom(conn, item_id)
        if not item:
            raise NotFoundError(
                "Barang tidak ditemukan.",
                details={"item_id": item_id, "line_index": idx},
            )
        if not item["is_active"]:
            raise InactiveReferenceError(
                f"Barang '{item['sku']}' berstatus tidak aktif.",
                details={"item_id": item_id, "sku": item["sku"], "line_index": idx},
            )
        _ensure_integer_if_required(
            qty, item=item, field_name="qty", extra={"line_index": idx}
        )
        normalized.append({"item_id": item_id, "qty": qty})

    return normalized


def _ensure_location_receivable(
    conn: Connection[dict[str, Any]], *, warehouse_id: int, location_id: int
) -> None:
    """Kunci lokasi tujuan (FOR SHARE) lalu pastikan aktif & tidak dibekukan Opname (PRD 5.1, 6.5, 6.6).

    Dilakukan eksplisit karena syarat ini berlaku walaupun seluruh qty_received = 0
    (tidak ada pemanggilan apply_movement yang akan memeriksanya).
    """
    loc = inventory_repo.lock_location_for_share(conn, location_id)
    if not loc or int(loc["warehouse_id"]) != int(warehouse_id):
        raise InvalidLocationError(
            "Lokasi tujuan tidak ditemukan atau bukan milik gudang tujuan.",
            details={"warehouse_id": warehouse_id, "location_id": location_id},
        )
    if not loc["is_active"]:
        raise InvalidLocationError(
            f"Lokasi tujuan '{loc['code']}' berstatus tidak aktif.",
            details={"warehouse_id": warehouse_id, "location_id": location_id},
        )
    if not loc["warehouse_is_active"]:
        raise InactiveReferenceError(
            "Gudang tujuan berstatus tidak aktif.",
            details={"warehouse_id": warehouse_id},
        )
    freezing = opname_repo.get_active_opname_freezing_location(
        conn, warehouse_id=warehouse_id, location_id=location_id
    )
    if freezing is not None:
        raise LocationFrozen(
            f"Lokasi '{loc['code']}' sedang dibekukan oleh sesi Stock Opname '{freezing['opname_number']}'.",
            details={
                "warehouse_id": warehouse_id,
                "location_id": location_id,
                "location_code": loc["code"],
                "opname_id": freezing["id"],
                "opname_number": freezing["opname_number"],
            },
        )


def _invalid_transition(
    transfer_id: int, current_status: str, target_status: str, message: str
) -> InvalidStateTransition:
    return InvalidStateTransition(
        message,
        details={
            "transfer_id": transfer_id,
            "current_status": current_status,
            "target_status": target_status,
        },
    )


def _serialize_snapshot(detail: dict[str, Any]) -> dict[str, Any]:
    """Representasi ringkas Transfer untuk old_values/new_values di audit_logs."""
    return {
        "id": detail["id"],
        "transfer_number": detail["transfer_number"],
        "source_warehouse_id": detail["source_warehouse_id"],
        "source_location_id": detail["source_location_id"],
        "destination_warehouse_id": detail["destination_warehouse_id"],
        "destination_location_id": detail["destination_location_id"],
        "status": detail["status"],
        "notes": detail["notes"],
        "lines": [
            {
                "id": ln["id"],
                "item_id": ln["item_id"],
                "item_sku": ln["item_sku"],
                "qty": f"{Decimal(ln['qty']):.4f}",
                "qty_received": f"{Decimal(ln['qty_received']):.4f}"
                if ln["qty_received"] is not None
                else None,
                "variance_reason": ln["variance_reason"],
            }
            for ln in detail.get("lines", [])
        ],
    }


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


# ============================================================================
# Use case: baca
# ============================================================================
def list_stock_transfers(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    warehouse_id: int | None = None,
    source_warehouse_id: int | None = None,
    destination_warehouse_id: int | None = None,
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
        allowed_columns=TRANSFER_SORT_COLUMNS,
        default_column="id",
        default_dir="DESC",
    )

    clean_status: str | None = None
    if status is not None:
        clean_status = status.strip().upper()
        if clean_status not in ALLOWED_TRANSFER_STATUSES:
            raise ValidationDomainError(
                f"Filter status Transfer '{status}' tidak valid.",
                details={
                    "status": status,
                    "allowed_values": sorted(ALLOWED_TRANSFER_STATUSES),
                },
            )

    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValidationDomainError(
            "Parameter date_from tidak boleh lebih besar dari date_to.",
            details={"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
        )

    # PRD 3.2 poin 5: Warehouse Staff hanya melihat Transfer yang asal ATAU tujuannya gudang yang ditugaskan
    scoped_ids = access_service.get_scoped_warehouse_ids_for_read(conn, actor)
    if scoped_ids is not None:
        for wh_filter in (warehouse_id, source_warehouse_id, destination_warehouse_id):
            if wh_filter is not None:
                access_service.ensure_warehouse_access(conn, actor, wh_filter)

    items, total = transfer_repo.list_transfers(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        scoped_warehouse_ids=scoped_ids,
        warehouse_id=warehouse_id,
        source_warehouse_id=source_warehouse_id,
        destination_warehouse_id=destination_warehouse_id,
        status=clean_status,
        date_from=date_from,
        date_to=date_to,
        search=search,
        order_by_sql=order_by_sql,
    )
    return {"items": items, "total": total, "limit": norm_limit, "offset": norm_offset}


def get_stock_transfer(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    transfer_id: int,
) -> dict[str, Any]:
    transfer = transfer_repo.get_transfer_by_id(conn, transfer_id)
    if not transfer:
        raise NotFoundError(
            "Transfer Stok tidak ditemukan.", details={"transfer_id": transfer_id}
        )

    scoped_ids = access_service.get_scoped_warehouse_ids_for_read(conn, actor)
    if scoped_ids is not None:
        related = {
            int(transfer["source_warehouse_id"]),
            int(transfer["destination_warehouse_id"]),
        }
        if not related.intersection(scoped_ids):
            raise WarehouseNotAssigned(
                "Anda tidak ditugaskan pada gudang asal maupun gudang tujuan Transfer ini.",
                details={
                    "transfer_id": transfer_id,
                    "source_warehouse_id": transfer["source_warehouse_id"],
                    "destination_warehouse_id": transfer["destination_warehouse_id"],
                    "assigned_warehouse_ids": scoped_ids,
                },
            )
    return transfer


# ============================================================================
# Use case: DRAFT
# ============================================================================
def create_stock_transfer(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    source_warehouse_id: int,
    source_location_id: int,
    destination_warehouse_id: int,
    destination_location_id: int,
    notes: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """(baru) -> DRAFT. transfer:create mensyaratkan penugasan pada gudang asal (PRD 3.2 poin 3)."""
    with conn.transaction():
        access_service.ensure_warehouse_access(conn, actor, source_warehouse_id)
        _validate_header(
            conn,
            source_warehouse_id=source_warehouse_id,
            source_location_id=source_location_id,
            destination_warehouse_id=destination_warehouse_id,
            destination_location_id=destination_location_id,
        )
        normalized_lines = _validate_and_normalize_lines(conn, lines or [])

        transfer_number = numbering_service.generate_document_number(conn, DocType.TRF)
        header = transfer_repo.insert_transfer_header(
            conn,
            transfer_number=transfer_number,
            source_warehouse_id=source_warehouse_id,
            source_location_id=source_location_id,
            destination_warehouse_id=destination_warehouse_id,
            destination_location_id=destination_location_id,
            notes=_clean_text(notes),
            created_by=int(actor["id"]),
        )
        transfer_id = int(header["id"])

        if normalized_lines:
            transfer_repo.update_transfer_lines(
                conn,
                transfer_id=transfer_id,
                lines=normalized_lines,
                actor_id=int(actor["id"]),
            )

        created = transfer_repo.get_transfer_by_id(conn, transfer_id)
        assert created is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="TRANSFER_CREATED",
            entity_type=ENTITY_TYPE,
            entity_id=transfer_id,
            old_values=None,
            new_values=_serialize_snapshot(created),
            ip_address=ip_address,
        )
        return created


def update_stock_transfer(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    transfer_id: int,
    source_warehouse_id: int | None = None,
    source_location_id: int | None = None,
    destination_warehouse_id: int | None = None,
    destination_location_id: int | None = None,
    notes: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Revisi Transfer yang masih DRAFT (transfer:create, penugasan gudang asal lama & baru)."""
    with conn.transaction():
        locked = transfer_repo.lock_transfer_by_id(conn, transfer_id)
        if not locked:
            raise NotFoundError(
                "Transfer Stok tidak ditemukan.", details={"transfer_id": transfer_id}
            )

        access_service.ensure_warehouse_access(
            conn, actor, int(locked["source_warehouse_id"])
        )

        if locked["status"] != TransferStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Transfer berstatus '{locked['status']}' tidak dapat diubah; hanya Transfer DRAFT yang dapat direvisi.",
                details={"transfer_id": transfer_id, "current_status": locked["status"]},
            )

        before = transfer_repo.get_transfer_by_id(conn, transfer_id)
        assert before is not None
        old_snapshot = _serialize_snapshot(before)

        new_src_wh = (
            source_warehouse_id
            if source_warehouse_id is not None
            else int(locked["source_warehouse_id"])
        )
        new_src_loc = (
            source_location_id
            if source_location_id is not None
            else int(locked["source_location_id"])
        )
        new_dst_wh = (
            destination_warehouse_id
            if destination_warehouse_id is not None
            else int(locked["destination_warehouse_id"])
        )
        new_dst_loc = (
            destination_location_id
            if destination_location_id is not None
            else int(locked["destination_location_id"])
        )
        new_notes = _clean_text(notes) if notes is not None else locked["notes"]

        if new_src_wh != int(locked["source_warehouse_id"]):
            access_service.ensure_warehouse_access(conn, actor, new_src_wh)

        _validate_header(
            conn,
            source_warehouse_id=new_src_wh,
            source_location_id=new_src_loc,
            destination_warehouse_id=new_dst_wh,
            destination_location_id=new_dst_loc,
        )

        transfer_repo.update_transfer_draft_header(
            conn,
            transfer_id,
            source_warehouse_id=new_src_wh,
            source_location_id=new_src_loc,
            destination_warehouse_id=new_dst_wh,
            destination_location_id=new_dst_loc,
            notes=new_notes,
        )

        if lines is not None:
            normalized_lines = _validate_and_normalize_lines(conn, lines)
            transfer_repo.update_transfer_lines(
                conn,
                transfer_id=transfer_id,
                lines=normalized_lines,
                actor_id=int(actor["id"]),
            )

        updated = transfer_repo.get_transfer_by_id(conn, transfer_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="TRANSFER_UPDATED",
            entity_type=ENTITY_TYPE,
            entity_id=transfer_id,
            old_values=old_snapshot,
            new_values=_serialize_snapshot(updated),
            ip_address=ip_address,
        )
        return updated


# ============================================================================
# Use case: transisi status
# ============================================================================
def approve_transfer(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    transfer_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """DRAFT -> APPROVED (transfer:approve, penugasan gudang asal; minimal 1 baris)."""
    with conn.transaction():
        locked = transfer_repo.lock_transfer_by_id(conn, transfer_id)
        if not locked:
            raise NotFoundError(
                "Transfer Stok tidak ditemukan.", details={"transfer_id": transfer_id}
            )
        if locked["status"] != TransferStatus.DRAFT.value:
            raise _invalid_transition(
                transfer_id,
                locked["status"],
                TransferStatus.APPROVED.value,
                f"Transfer berstatus '{locked['status']}' tidak dapat disetujui (harus berstatus DRAFT).",
            )

        access_service.ensure_warehouse_access(
            conn, actor, int(locked["source_warehouse_id"])
        )

        lines = transfer_repo.list_transfer_lines(conn, transfer_id)
        if not lines:
            raise ValidationDomainError(
                "Transfer tidak dapat disetujui karena belum memiliki baris barang.",
                details={"transfer_id": transfer_id},
            )

        transfer_repo.update_transfer_approved(
            conn, transfer_id, approved_by=int(actor["id"])
        )
        updated = transfer_repo.get_transfer_by_id(conn, transfer_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="TRANSFER_APPROVED",
            entity_type=ENTITY_TYPE,
            entity_id=transfer_id,
            old_values={"status": TransferStatus.DRAFT.value},
            new_values={
                "status": TransferStatus.APPROVED.value,
                "approved_by": updated["approved_by"],
                "approved_at": updated["approved_at"].isoformat()
                if updated["approved_at"]
                else None,
            },
            ip_address=ip_address,
        )
        return updated


def ship_transfer(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    transfer_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """APPROVED -> SHIPPED secara atomik: kurangi stok asal & tulis ledger OUT_TRANSFER (AC-02, AC-03, AC-06).

    Urutan penguncian (PRD 6.5): header Transfer (FOR UPDATE) -> lokasi asal (FOR SHARE, di apply_movement)
    -> saldo stok diurutkan (warehouse_id, location_id, item_id).
    """
    with conn.transaction():
        # 1. Kunci header & jaga status yang diharapkan
        locked = transfer_repo.lock_transfer_by_id(conn, transfer_id)
        if not locked:
            raise NotFoundError(
                "Transfer Stok tidak ditemukan.", details={"transfer_id": transfer_id}
            )
        if locked["status"] != TransferStatus.APPROVED.value:
            raise _invalid_transition(
                transfer_id,
                locked["status"],
                TransferStatus.SHIPPED.value,
                f"Transfer berstatus '{locked['status']}' tidak dapat dikirim (harus berstatus APPROVED).",
            )

        source_wh = int(locked["source_warehouse_id"])
        source_loc = int(locked["source_location_id"])

        # 2. transfer:ship mensyaratkan penugasan pada gudang asal (PRD 3.2 poin 3)
        access_service.ensure_warehouse_access(conn, actor, source_wh)

        lines = transfer_repo.list_transfer_lines(conn, transfer_id)
        if not lines:
            raise ValidationDomainError(
                "Transfer tidak memiliki baris barang untuk dikirim.",
                details={"transfer_id": transfer_id},
            )

        # 3-4. Mutasi saldo per baris, diurutkan (warehouse_id, location_id, item_id).
        #      apply_movement mengunci lokasi (FOR SHARE), memeriksa pembekuan (LOCATION_FROZEN),
        #      mengunci saldo (FOR UPDATE), dan menolak stok negatif (INSUFFICIENT_STOCK).
        for ln in sorted(lines, key=lambda r: (source_wh, source_loc, int(r["item_id"]))):
            qty = Decimal(ln["qty"]).quantize(FOUR_PLACES)
            inventory_service.apply_movement(
                conn,
                movement_type=MovementType.OUT_TRANSFER,
                warehouse_id=source_wh,
                location_id=source_loc,
                item_id=int(ln["item_id"]),
                qty_change=-qty,
                reference_type=ReferenceType.STOCK_TRANSFER,
                reference_id=transfer_id,
                created_by=int(actor["id"]),
                notes=f"Pengiriman Transfer {locked['transfer_number']}",
            )

        # 5. Tandai SHIPPED
        transfer_repo.update_transfer_shipped(
            conn, transfer_id, shipped_by=int(actor["id"])
        )
        shipped = transfer_repo.get_transfer_by_id(conn, transfer_id)
        assert shipped is not None

        # 6. Audit log dalam transaksi yang sama
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="TRANSFER_SHIPPED",
            entity_type=ENTITY_TYPE,
            entity_id=transfer_id,
            old_values={"status": TransferStatus.APPROVED.value},
            new_values={
                "status": TransferStatus.SHIPPED.value,
                "shipped_by": shipped["shipped_by"],
                "shipped_at": shipped["shipped_at"].isoformat()
                if shipped["shipped_at"]
                else None,
                "lines": [
                    {"item_id": ln["item_id"], "qty": f"{Decimal(ln['qty']):.4f}"}
                    for ln in shipped["lines"]
                ],
            },
            ip_address=ip_address,
        )
        return shipped


def receive_transfer(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    transfer_id: int,
    lines: list[dict[str, Any]],
    ip_address: str | None = None,
) -> dict[str, Any]:
    """SHIPPED -> RECEIVED secara atomik: tambah stok tujuan sebesar qty_received & tulis ledger IN_TRANSFER (AC-03, AC-09).

    Aturan selisih (PRD 6.7): qty_received <= qty (TRANSFER_QTY_EXCEEDS_SHIPPED), alasan wajib bila kurang
    (VALIDATION_ERROR), selisih tidak dikembalikan ke asal dan tidak menghasilkan ledger.
    Penerimaan bersifat final satu kali per dokumen, sehingga seluruh baris wajib diisi.
    """
    with conn.transaction():
        # 1. Kunci header & jaga status yang diharapkan
        locked = transfer_repo.lock_transfer_by_id(conn, transfer_id)
        if not locked:
            raise NotFoundError(
                "Transfer Stok tidak ditemukan.", details={"transfer_id": transfer_id}
            )
        if locked["status"] != TransferStatus.SHIPPED.value:
            raise _invalid_transition(
                transfer_id,
                locked["status"],
                TransferStatus.RECEIVED.value,
                f"Transfer berstatus '{locked['status']}' tidak dapat diterima (harus berstatus SHIPPED).",
            )

        dest_wh = int(locked["destination_warehouse_id"])
        dest_loc = int(locked["destination_location_id"])

        # 2. transfer:receive mensyaratkan penugasan pada gudang tujuan (PRD 3.2 poin 3)
        access_service.ensure_warehouse_access(conn, actor, dest_wh)

        # 3. Validasi payload penerimaan terhadap baris Transfer
        transfer_lines = transfer_repo.list_transfer_lines(conn, transfer_id)
        lines_by_id = {int(ln["id"]): ln for ln in transfer_lines}

        received_map: dict[int, dict[str, Any]] = {}
        for idx, entry in enumerate(lines):
            line_id = int(entry["line_id"])
            if line_id not in lines_by_id:
                raise ValidationDomainError(
                    "Baris Transfer (line_id) tidak ditemukan pada dokumen ini.",
                    details={"transfer_id": transfer_id, "line_id": line_id, "line_index": idx},
                )
            if line_id in received_map:
                raise ValidationDomainError(
                    "Baris Transfer (line_id) tidak boleh duplikat pada penerimaan.",
                    details={"line_id": line_id, "line_index": idx},
                )

            tl = lines_by_id[line_id]
            qty_shipped = Decimal(tl["qty"]).quantize(FOUR_PLACES)
            qty_received = _normalize_qty(
                entry["qty_received"], field_name="qty_received", allow_zero=True
            )

            if qty_received > qty_shipped:
                raise TransferQtyExceedsShipped(
                    f"qty_received ({qty_received:.4f}) melebihi kuantitas yang dikirim ({qty_shipped:.4f}).",
                    details={
                        "line_id": line_id,
                        "item_id": tl["item_id"],
                        "item_sku": tl["item_sku"],
                        "qty_shipped": f"{qty_shipped:.4f}",
                        "qty_received": f"{qty_received:.4f}",
                    },
                )

            reason = _clean_text(entry.get("variance_reason"))
            if qty_received < qty_shipped and reason is None:
                raise ValidationDomainError(
                    "Alasan selisih (variance_reason) wajib diisi bila qty_received lebih kecil dari kuantitas yang dikirim.",
                    details={
                        "line_id": line_id,
                        "item_id": tl["item_id"],
                        "item_sku": tl["item_sku"],
                        "qty_shipped": f"{qty_shipped:.4f}",
                        "qty_received": f"{qty_received:.4f}",
                        "field": "variance_reason",
                    },
                )

            _ensure_integer_if_required(
                qty_received,
                item={
                    "id": tl["item_id"],
                    "sku": tl["item_sku"],
                    "uom_code": tl["uom_code"],
                    "allow_decimal": tl["allow_decimal"],
                },
                field_name="qty_received",
                extra={"line_id": line_id},
            )

            received_map[line_id] = {
                "qty_received": qty_received,
                # Alasan hanya relevan bila ada selisih
                "variance_reason": reason if qty_received < qty_shipped else None,
            }

        missing = sorted(set(lines_by_id) - set(received_map))
        if missing:
            raise ValidationDomainError(
                "Penerimaan Transfer bersifat final; seluruh baris Transfer wajib diisi qty_received.",
                details={"transfer_id": transfer_id, "missing_line_ids": missing},
            )

        # 4. Kunci lokasi tujuan (FOR SHARE) & pastikan aktif serta tidak dibekukan (PRD 6.5 langkah 3, 6.6)
        _ensure_location_receivable(conn, warehouse_id=dest_wh, location_id=dest_loc)

        # 5. Mutasi saldo tujuan hanya untuk qty_received > 0, diurutkan (warehouse_id, location_id, item_id)
        for tl in sorted(transfer_lines, key=lambda r: (dest_wh, dest_loc, int(r["item_id"]))):
            qty_received = received_map[int(tl["id"])]["qty_received"]
            if qty_received > ZERO:
                inventory_service.apply_movement(
                    conn,
                    movement_type=MovementType.IN_TRANSFER,
                    warehouse_id=dest_wh,
                    location_id=dest_loc,
                    item_id=int(tl["item_id"]),
                    qty_change=qty_received,
                    reference_type=ReferenceType.STOCK_TRANSFER,
                    reference_id=transfer_id,
                    created_by=int(actor["id"]),
                    notes=f"Penerimaan Transfer {locked['transfer_number']}",
                )

        # 6. Simpan qty_received & alasan selisih pada baris Transfer
        for line_id in sorted(received_map):
            transfer_repo.update_transfer_line_received(
                conn,
                line_id=line_id,
                qty_received=received_map[line_id]["qty_received"],
                variance_reason=received_map[line_id]["variance_reason"],
            )

        # 7. Tandai RECEIVED
        transfer_repo.update_transfer_received(
            conn, transfer_id, received_by=int(actor["id"])
        )
        received = transfer_repo.get_transfer_by_id(conn, transfer_id)
        assert received is not None

        # 8. Audit log dalam transaksi yang sama
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="TRANSFER_RECEIVED",
            entity_type=ENTITY_TYPE,
            entity_id=transfer_id,
            old_values={"status": TransferStatus.SHIPPED.value},
            new_values={
                "status": TransferStatus.RECEIVED.value,
                "received_by": received["received_by"],
                "received_at": received["received_at"].isoformat()
                if received["received_at"]
                else None,
                "lines": [
                    {
                        "id": ln["id"],
                        "item_id": ln["item_id"],
                        "qty": f"{Decimal(ln['qty']):.4f}",
                        "qty_received": f"{Decimal(ln['qty_received']):.4f}",
                        "qty_variance": f"{Decimal(ln['qty_variance']):.4f}",
                        "variance_reason": ln["variance_reason"],
                    }
                    for ln in received["lines"]
                ],
            },
            ip_address=ip_address,
        )
        return received


def cancel_transfer(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    transfer_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """DRAFT -> CANCELLED (transfer:create) atau APPROVED -> CANCELLED (transfer:approve) (PRD 5.1).

    Kedua permission mensyaratkan penugasan pada gudang asal (PRD 3.2 poin 3).
    """
    with conn.transaction():
        locked = transfer_repo.lock_transfer_by_id(conn, transfer_id)
        if not locked:
            raise NotFoundError(
                "Transfer Stok tidak ditemukan.", details={"transfer_id": transfer_id}
            )

        current_status = str(locked["status"])
        actor_perms: set[str] = set(actor.get("permissions", []))

        if current_status == TransferStatus.DRAFT.value:
            required = TRANSFER_CREATE
        elif current_status == TransferStatus.APPROVED.value:
            required = TRANSFER_APPROVE
        else:
            raise _invalid_transition(
                transfer_id,
                current_status,
                TransferStatus.CANCELLED.value,
                f"Transfer berstatus '{current_status}' tidak dapat dibatalkan.",
            )

        if required not in actor_perms:
            raise PermissionDenied(
                f"Anda tidak memiliki izin '{required}' untuk membatalkan Transfer berstatus {current_status}.",
                details={"required_permission": required},
            )

        access_service.ensure_warehouse_access(
            conn, actor, int(locked["source_warehouse_id"])
        )

        transfer_repo.update_transfer_cancelled(conn, transfer_id)
        updated = transfer_repo.get_transfer_by_id(conn, transfer_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="TRANSFER_CANCELLED",
            entity_type=ENTITY_TYPE,
            entity_id=transfer_id,
            old_values={"status": current_status},
            new_values={"status": TransferStatus.CANCELLED.value},
            ip_address=ip_address,
        )
        return updated

