"""Service logika bisnis Stock Opname: DRAFT -> IN_PROGRESS -> WAITING_APPROVAL -> COMPLETED (FR-07, PRD 5.1, 6.5, 6.6).

AC terkait: AC-04 (rekonsiliasi Stock Opname), AC-05 (RBAC & Audit Log), AC-07 (atomisitas transaksi),
AC-10 (pembekuan lokasi Opname), AC-12 (warehouse scoping), AC-13 (pencegahan pemrosesan ganda).
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
    ValidationDomainError,
)
from app.repositories import inventory_repo, opname_repo, warehouse_repo
from app.services import (
    access_service,
    audit_service,
    inventory_service,
    numbering_service,
)
from app.utils.enums import DocType, MovementType, OpnameStatus, ReferenceType
from app.utils.pagination import build_order_by, normalize_pagination

FOUR_PLACES = Decimal("0.0001")
ZERO = Decimal("0.0000")
ENTITY_TYPE = "stock_opnames"

OPNAME_SORT_COLUMNS: dict[str, str] = {
    "id": "so.id",
    "opname_number": "so.opname_number",
    "status": "so.status",
    "created_at": "so.created_at",
    "started_at": "so.started_at",
    "approved_at": "so.approved_at",
}

ALLOWED_OPNAME_STATUSES: frozenset[str] = frozenset(s.value for s in OpnameStatus)
CANCELLABLE_OPNAME_STATUSES: frozenset[str] = frozenset(
    {OpnameStatus.DRAFT.value, OpnameStatus.IN_PROGRESS.value}
)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_non_negative_qty(value: Any, *, field_name: str = "qty_physical") -> Decimal:
    """Memastikan qty_physical bertipe Decimal >= 0 dengan maksimum 4 angka di belakang koma (FR-07, PRD 6.9)."""
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
    if quantized < ZERO:
        raise ValidationDomainError(
            f"Field '{field_name}' tidak boleh bernilai negatif (harus >= 0).",
            details={"field": field_name, "value": str(quantized)},
        )
    return quantized


def _validate_warehouse_and_optional_location(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int | None,
) -> None:
    """Memastikan gudang aktif (INACTIVE_REFERENCE) dan lokasi (bila diisi) aktif & milik gudang tsb (INVALID_LOCATION)."""
    warehouse = warehouse_repo.get_warehouse_by_id(conn, warehouse_id)
    if not warehouse:
        raise NotFoundError(
            "Gudang tidak ditemukan.",
            details={"warehouse_id": warehouse_id},
        )
    if not warehouse["is_active"]:
        raise InactiveReferenceError(
            f"Gudang '{warehouse['code']}' berstatus tidak aktif.",
            details={"warehouse_id": warehouse_id},
        )

    if location_id is not None:
        loc = warehouse_repo.get_location_by_id(conn, location_id)
        if not loc or int(loc["warehouse_id"]) != int(warehouse_id):
            raise InvalidLocationError(
                "Lokasi penyimpanan tidak ditemukan atau bukan milik gudang yang dipilih.",
                details={"warehouse_id": warehouse_id, "location_id": location_id},
            )
        if not loc["is_active"]:
            raise InvalidLocationError(
                f"Lokasi penyimpanan '{loc['code']}' berstatus tidak aktif.",
                details={"warehouse_id": warehouse_id, "location_id": location_id},
            )


def _serialize_snapshot(detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": detail["id"],
        "opname_number": detail["opname_number"],
        "warehouse_id": detail["warehouse_id"],
        "location_id": detail["location_id"],
        "status": detail["status"],
        "notes": detail["notes"],
        "rejection_reason": detail["rejection_reason"],
        "lines": [
            {
                "id": ln["id"],
                "location_id": ln["location_id"],
                "item_id": ln["item_id"],
                "item_sku": ln["item_sku"],
                "qty_system": f"{Decimal(ln['qty_system']):.4f}",
                "qty_physical": f"{Decimal(ln['qty_physical']):.4f}"
                if ln["qty_physical"] is not None
                else None,
                "qty_variance": f"{Decimal(ln['qty_variance']):.4f}"
                if ln["qty_variance"] is not None
                else None,
            }
            for ln in detail.get("lines", [])
        ],
    }


def list_stock_opnames(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    warehouse_id: int | None = None,
    location_id: int | None = None,
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
        allowed_columns=OPNAME_SORT_COLUMNS,
        default_column="id",
        default_dir="DESC",
    )

    clean_status: str | None = None
    if status is not None:
        clean_status = status.strip().upper()
        if clean_status not in ALLOWED_OPNAME_STATUSES:
            raise ValidationDomainError(
                f"Filter status Stock Opname '{status}' tidak valid.",
                details={
                    "status": status,
                    "allowed_values": sorted(ALLOWED_OPNAME_STATUSES),
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

    scoped_ids = access_service.get_scoped_warehouse_ids_for_read(conn, actor)
    if scoped_ids is not None and warehouse_id is not None:
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

    items, total = opname_repo.list_opnames(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        scoped_warehouse_ids=scoped_ids,
        warehouse_id=warehouse_id,
        location_id=location_id,
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


def get_stock_opname(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    opname_id: int,
) -> dict[str, Any]:
    opname = opname_repo.get_opname_by_id(conn, opname_id)
    if not opname:
        raise NotFoundError(
            "Sesi Stock Opname tidak ditemukan.",
            details={"opname_id": opname_id},
        )

    scoped_ids = access_service.get_scoped_warehouse_ids_for_read(conn, actor)
    if scoped_ids is not None:
        access_service.ensure_warehouse_access(conn, actor, int(opname["warehouse_id"]))
    return opname


def create_stock_opname(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    warehouse_id: int,
    location_id: int | None = None,
    notes: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """(baru) -> DRAFT (opname:manage, penugasan pada gudang terkait; FR-07, PRD 5.1)."""
    with conn.transaction():
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)
        _validate_warehouse_and_optional_location(
            conn, warehouse_id=warehouse_id, location_id=location_id
        )

        opname_number = numbering_service.generate_document_number(conn, DocType.OPN)
        header = opname_repo.insert_opname_header(
            conn,
            opname_number=opname_number,
            warehouse_id=warehouse_id,
            location_id=location_id,
            notes=_clean_text(notes),
            created_by=int(actor["id"]),
        )
        opname_id = int(header["id"])

        created = opname_repo.get_opname_by_id(conn, opname_id)
        assert created is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="OPNAME_CREATED",
            entity_type=ENTITY_TYPE,
            entity_id=opname_id,
            old_values=None,
            new_values=_serialize_snapshot(created),
            ip_address=ip_address,
        )
        return created


def update_stock_opname(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    opname_id: int,
    location_id: int | None = None,
    clear_location: bool = False,
    notes: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Memperbarui sesi Stock Opname yang masih berstatus DRAFT."""
    with conn.transaction():
        locked = opname_repo.lock_opname_by_id(conn, opname_id)
        if not locked:
            raise NotFoundError(
                "Sesi Stock Opname tidak ditemukan.",
                details={"opname_id": opname_id},
            )

        warehouse_id = int(locked["warehouse_id"])
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        if locked["status"] != OpnameStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Stock Opname berstatus '{locked['status']}' tidak dapat diubah; hanya Opname berstatus DRAFT yang dapat direvisi.",
                details={"opname_id": opname_id, "current_status": locked["status"]},
            )

        before = opname_repo.get_opname_by_id(conn, opname_id)
        assert before is not None
        old_snapshot = _serialize_snapshot(before)

        if clear_location:
            new_location_id = None
        elif location_id is not None:
            new_location_id = location_id
        else:
            new_location_id = locked["location_id"]

        new_notes = _clean_text(notes) if notes is not None else locked["notes"]

        _validate_warehouse_and_optional_location(
            conn, warehouse_id=warehouse_id, location_id=new_location_id
        )

        opname_repo.update_opname_draft_header(
            conn,
            opname_id,
            location_id=new_location_id,
            notes=new_notes,
        )
        updated = opname_repo.get_opname_by_id(conn, opname_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="OPNAME_UPDATED",
            entity_type=ENTITY_TYPE,
            entity_id=opname_id,
            old_values=old_snapshot,
            new_values=_serialize_snapshot(updated),
            ip_address=ip_address,
        )
        return updated


def start_stock_opname(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    opname_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """DRAFT -> IN_PROGRESS: mengunci lokasi (FOR UPDATE), memeriksa tumpang tindih pembekuan, dan mengambil snapshot qty_system (FR-07, PRD 5.1, 6.5, 6.6)."""
    with conn.transaction():
        # 1. Kunci header Opname (FOR UPDATE) & pastikan status DRAFT
        locked = opname_repo.lock_opname_by_id(conn, opname_id)
        if not locked:
            raise NotFoundError(
                "Sesi Stock Opname tidak ditemukan.",
                details={"opname_id": opname_id},
            )
        if locked["status"] != OpnameStatus.DRAFT.value:
            raise InvalidStateTransition(
                f"Stock Opname berstatus '{locked['status']}' tidak dapat dimulai (harus berstatus DRAFT).",
                details={
                    "opname_id": opname_id,
                    "current_status": locked["status"],
                    "target_status": OpnameStatus.IN_PROGRESS.value,
                },
            )

        warehouse_id = int(locked["warehouse_id"])
        location_id: int | None = (
            int(locked["location_id"]) if locked["location_id"] is not None else None
        )

        # 2. Periksa penugasan gudang (AC-12)
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        _validate_warehouse_and_optional_location(
            conn, warehouse_id=warehouse_id, location_id=location_id
        )

        # 3. Kunci lokasi dalam cakupan dengan FOR UPDATE diurutkan id ASC (PRD 6.5 langkah 3)
        locked_locations = opname_repo.lock_scope_locations_for_update(
            conn, warehouse_id=warehouse_id, location_id=location_id
        )
        if not locked_locations or not any(loc["is_active"] for loc in locked_locations):
            raise InvalidLocationError(
                "Tidak ada lokasi penyimpanan aktif pada cakupan Stock Opname ini.",
                details={"warehouse_id": warehouse_id, "location_id": location_id},
            )

        # 4. Pastikan tidak ada sesi Opname aktif lain pada lokasi dalam cakupan (FR-07, PRD 5.1, 6.6)
        overlapping = opname_repo.get_active_overlapping_opname(
            conn,
            warehouse_id=warehouse_id,
            location_id=location_id,
            exclude_opname_id=opname_id,
        )
        if overlapping is not None:
            raise LocationFrozen(
                f"Lokasi dalam cakupan sedang dibekukan oleh sesi Stock Opname aktif '{overlapping['opname_number']}'.",
                details={
                    "warehouse_id": warehouse_id,
                    "location_id": location_id,
                    "active_opname_id": overlapping["id"],
                    "active_opname_number": overlapping["opname_number"],
                },
            )

        # 5. Ambil snapshot qty_system dari inventory_balances (urut warehouse_id, location_id, item_id)
        snapshot_rows = opname_repo.lock_scope_balances_for_snapshot(
            conn, warehouse_id=warehouse_id, location_id=location_id
        )
        if snapshot_rows:
            opname_repo.insert_snapshot_lines(
                conn,
                opname_id=opname_id,
                warehouse_id=warehouse_id,
                snapshot_rows=snapshot_rows,
                actor_id=int(actor["id"]),
            )

        # 6. Tandai IN_PROGRESS (mulai membekukan lokasi dalam cakupan)
        opname_repo.update_opname_started(
            conn, opname_id, started_by=int(actor["id"])
        )
        started = opname_repo.get_opname_by_id(conn, opname_id)
        assert started is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="OPNAME_STARTED",
            entity_type=ENTITY_TYPE,
            entity_id=opname_id,
            old_values={"status": OpnameStatus.DRAFT.value},
            new_values=_serialize_snapshot(started),
            ip_address=ip_address,
        )
        return started


def record_opname_counts(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    opname_id: int,
    lines: list[dict[str, Any]],
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Mengisi qty_physical >= 0 per baris dan/atau menambahkan baris barang baru dengan qty_system = 0 saat IN_PROGRESS (FR-07)."""
    with conn.transaction():
        locked = opname_repo.lock_opname_by_id(conn, opname_id)
        if not locked:
            raise NotFoundError(
                "Sesi Stock Opname tidak ditemukan.",
                details={"opname_id": opname_id},
            )
        if locked["status"] != OpnameStatus.IN_PROGRESS.value:
            raise InvalidStateTransition(
                f"Hasil hitung fisik hanya dapat diisi saat sesi Stock Opname berstatus IN_PROGRESS (status saat ini: '{locked['status']}').",
                details={"opname_id": opname_id, "current_status": locked["status"]},
            )

        warehouse_id = int(locked["warehouse_id"])
        scope_location_id: int | None = (
            int(locked["location_id"]) if locked["location_id"] is not None else None
        )
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        before = opname_repo.get_opname_by_id(conn, opname_id)
        assert before is not None
        old_snapshot = _serialize_snapshot(before)

        for idx, entry in enumerate(lines):
            qty_physical = _normalize_non_negative_qty(
                entry["qty_physical"], field_name="qty_physical"
            )
            clean_notes = _clean_text(entry.get("notes"))
            line_id = entry.get("line_id")

            if line_id is not None:
                existing_line = opname_repo.get_opname_line_by_id(
                    conn, opname_id=opname_id, line_id=int(line_id)
                )
                if not existing_line:
                    raise NotFoundError(
                        "Baris Stock Opname (line_id) tidak ditemukan pada sesi ini.",
                        details={
                            "opname_id": opname_id,
                            "line_id": int(line_id),
                            "line_index": idx,
                        },
                    )
                item = inventory_repo.get_item_with_uom(
                    conn, int(existing_line["item_id"])
                )
                assert item is not None
                if not bool(item["allow_decimal"]) and qty_physical != qty_physical.to_integral_value():
                    raise ValidationDomainError(
                        f"Barang '{item['sku']}' menggunakan UoM '{item['uom_code']}' yang harus berupa bilangan bulat.",
                        details={
                            "item_id": item["id"],
                            "sku": item["sku"],
                            "uom_code": item["uom_code"],
                            "qty_physical": str(qty_physical),
                            "line_index": idx,
                        },
                    )
                opname_repo.update_opname_counted_line(
                    conn,
                    line_id=int(existing_line["id"]),
                    qty_physical=qty_physical,
                    counted_by=int(actor["id"]),
                    notes=clean_notes,
                )
            else:
                target_loc_id = (
                    int(entry["location_id"])
                    if entry.get("location_id") is not None
                    else scope_location_id
                )
                target_item_id = (
                    int(entry["item_id"])
                    if entry.get("item_id") is not None
                    else None
                )
                if target_loc_id is None or target_item_id is None:
                    raise ValidationDomainError(
                        "Setiap baris hitung fisik wajib menyertakan line_id atau pasangan (location_id, item_id).",
                        details={"line_index": idx},
                    )

                if scope_location_id is not None and target_loc_id != scope_location_id:
                    raise InvalidLocationError(
                        "Lokasi yang dipilih berada di luar cakupan lokasi sesi Stock Opname ini.",
                        details={
                            "opname_id": opname_id,
                            "scope_location_id": scope_location_id,
                            "location_id": target_loc_id,
                            "line_index": idx,
                        },
                    )

                loc = warehouse_repo.get_location_by_id(conn, target_loc_id)
                if not loc or int(loc["warehouse_id"]) != warehouse_id or not loc["is_active"]:
                    raise InvalidLocationError(
                        "Lokasi penyimpanan tidak ditemukan, tidak aktif, atau bukan milik gudang sesi Opname.",
                        details={
                            "warehouse_id": warehouse_id,
                            "location_id": target_loc_id,
                            "line_index": idx,
                        },
                    )

                item = inventory_repo.get_item_with_uom(conn, target_item_id)
                if not item:
                    raise NotFoundError(
                        "Barang tidak ditemukan.",
                        details={"item_id": target_item_id, "line_index": idx},
                    )
                if not item["is_active"]:
                    raise InactiveReferenceError(
                        f"Barang '{item['sku']}' berstatus tidak aktif.",
                        details={
                            "item_id": target_item_id,
                            "sku": item["sku"],
                            "line_index": idx,
                        },
                    )
                if not bool(item["allow_decimal"]) and qty_physical != qty_physical.to_integral_value():
                    raise ValidationDomainError(
                        f"Barang '{item['sku']}' menggunakan UoM '{item['uom_code']}' yang harus berupa bilangan bulat.",
                        details={
                            "item_id": item["id"],
                            "sku": item["sku"],
                            "uom_code": item["uom_code"],
                            "qty_physical": str(qty_physical),
                            "line_index": idx,
                        },
                    )

                existing_by_key = opname_repo.get_opname_line_by_loc_item(
                    conn,
                    opname_id=opname_id,
                    location_id=target_loc_id,
                    item_id=target_item_id,
                )
                if existing_by_key:
                    opname_repo.update_opname_counted_line(
                        conn,
                        line_id=int(existing_by_key["id"]),
                        qty_physical=qty_physical,
                        counted_by=int(actor["id"]),
                        notes=clean_notes,
                    )
                else:
                    qty_system = opname_repo.get_balance_qty_on_hand(
                        conn,
                        warehouse_id=warehouse_id,
                        location_id=target_loc_id,
                        item_id=target_item_id,
                    )
                    opname_repo.insert_opname_counted_line(
                        conn,
                        opname_id=opname_id,
                        warehouse_id=warehouse_id,
                        location_id=target_loc_id,
                        item_id=target_item_id,
                        qty_system=qty_system,
                        qty_physical=qty_physical,
                        counted_by=int(actor["id"]),
                        notes=clean_notes,
                    )

        updated = opname_repo.get_opname_by_id(conn, opname_id)
        assert updated is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="OPNAME_COUNTED",
            entity_type=ENTITY_TYPE,
            entity_id=opname_id,
            old_values=old_snapshot,
            new_values=_serialize_snapshot(updated),
            ip_address=ip_address,
        )
        return updated


def submit_stock_opname(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    opname_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """IN_PROGRESS -> WAITING_APPROVAL: seluruh baris wajib memiliki qty_physical >= 0 (FR-07, PRD 5.1)."""
    with conn.transaction():
        locked = opname_repo.lock_opname_by_id(conn, opname_id)
        if not locked:
            raise NotFoundError(
                "Sesi Stock Opname tidak ditemukan.",
                details={"opname_id": opname_id},
            )
        if locked["status"] != OpnameStatus.IN_PROGRESS.value:
            raise InvalidStateTransition(
                f"Stock Opname berstatus '{locked['status']}' tidak dapat diajukan (harus berstatus IN_PROGRESS).",
                details={
                    "opname_id": opname_id,
                    "current_status": locked["status"],
                    "target_status": OpnameStatus.WAITING_APPROVAL.value,
                },
            )

        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))

        lines = opname_repo.list_opname_lines(conn, opname_id)
        if not lines:
            raise ValidationDomainError(
                "Sesi Stock Opname tidak dapat diajukan karena belum memiliki baris barang untuk dihitung.",
                details={"opname_id": opname_id},
            )

        uncounted = [int(ln["id"]) for ln in lines if ln["qty_physical"] is None]
        if uncounted:
            raise ValidationDomainError(
                "Seluruh baris Stock Opname wajib diisi qty_physical sebelum diajukan persetujuan.",
                details={"opname_id": opname_id, "uncounted_line_ids": uncounted},
            )

        opname_repo.update_opname_submitted(
            conn, opname_id, submitted_by=int(actor["id"])
        )
        submitted = opname_repo.get_opname_by_id(conn, opname_id)
        assert submitted is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="OPNAME_SUBMITTED",
            entity_type=ENTITY_TYPE,
            entity_id=opname_id,
            old_values={"status": OpnameStatus.IN_PROGRESS.value},
            new_values={
                "status": OpnameStatus.WAITING_APPROVAL.value,
                "submitted_by": submitted["submitted_by"],
                "submitted_at": submitted["submitted_at"].isoformat()
                if submitted["submitted_at"]
                else None,
            },
            ip_address=ip_address,
        )
        return submitted


def approve_stock_opname(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    opname_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """WAITING_APPROVAL -> COMPLETED secara atomik: samakan saldo dengan qty_physical, tulis ledger ADJUSTMENT_PLUS/MINUS untuk baris berselisih, dan lepas pembekuan (AC-04, AC-07, AC-10, AC-13)."""
    with conn.transaction():
        # 1. Kunci header Opname (FOR UPDATE) & pastikan status WAITING_APPROVAL
        locked = opname_repo.lock_opname_by_id(conn, opname_id)
        if not locked:
            raise NotFoundError(
                "Sesi Stock Opname tidak ditemukan.",
                details={"opname_id": opname_id},
            )
        if locked["status"] != OpnameStatus.WAITING_APPROVAL.value:
            raise InvalidStateTransition(
                f"Stock Opname berstatus '{locked['status']}' tidak dapat disetujui (harus berstatus WAITING_APPROVAL).",
                details={
                    "opname_id": opname_id,
                    "current_status": locked["status"],
                    "target_status": OpnameStatus.COMPLETED.value,
                },
            )

        warehouse_id = int(locked["warehouse_id"])
        # 2. Periksa penugasan gudang (AC-12)
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        lines = opname_repo.list_opname_lines(conn, opname_id)
        if not lines or any(ln["qty_physical"] is None for ln in lines):
            raise ValidationDomainError(
                "Seluruh baris Stock Opname wajib memiliki qty_physical sebelum disetujui.",
                details={"opname_id": opname_id},
            )

        # 3. Kunci lokasi penyimpanan dalam urutan id ASC (PRD 6.5 langkah 3)
        unique_loc_ids = sorted({int(ln["location_id"]) for ln in lines})
        for loc_id in unique_loc_ids:
            inventory_repo.lock_location_for_share(conn, loc_id)

        # 4. Urutkan baris berdasarkan (warehouse_id, location_id, item_id) (PRD 6.5 langkah 4)
        #    dan terapkan penyesuaian stok HANYA untuk baris dengan qty_variance != 0 (FR-07)
        sorted_lines = sorted(
            lines,
            key=lambda ln: (
                int(ln["warehouse_id"]),
                int(ln["location_id"]),
                int(ln["item_id"]),
            ),
        )
        for ln in sorted_lines:
            variance = Decimal(ln["qty_variance"]).quantize(FOUR_PLACES)
            if variance == ZERO:
                continue

            movement_type = (
                MovementType.ADJUSTMENT_PLUS
                if variance > ZERO
                else MovementType.ADJUSTMENT_MINUS
            )
            inventory_service.apply_movement(
                conn,
                movement_type=movement_type,
                warehouse_id=warehouse_id,
                location_id=int(ln["location_id"]),
                item_id=int(ln["item_id"]),
                qty_change=variance,
                reference_type=ReferenceType.STOCK_OPNAME,
                reference_id=opname_id,
                created_by=int(actor["id"]),
                notes=ln.get("notes")
                or f"Rekonsiliasi Stock Opname {locked['opname_number']}",
            )

        # 5. Tandai COMPLETED (otomatis melepas pembekuan lokasi)
        opname_repo.update_opname_completed(
            conn, opname_id, approved_by=int(actor["id"])
        )
        completed = opname_repo.get_opname_by_id(conn, opname_id)
        assert completed is not None

        # 6. Catat audit log dalam transaksi yang sama
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="OPNAME_APPROVED",
            entity_type=ENTITY_TYPE,
            entity_id=opname_id,
            old_values={"status": OpnameStatus.WAITING_APPROVAL.value},
            new_values=_serialize_snapshot(completed),
            ip_address=ip_address,
        )
        return completed


def reject_stock_opname(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    opname_id: int,
    rejection_reason: str,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """WAITING_APPROVAL -> IN_PROGRESS dengan alasan penolakan wajib untuk dihitung ulang (FR-07, PRD 5.1)."""
    clean_reason = _clean_text(rejection_reason)
    if not clean_reason:
        raise ValidationDomainError(
            "Alasan penolakan (rejection_reason) wajib diisi.",
            details={"field": "rejection_reason"},
        )

    with conn.transaction():
        locked = opname_repo.lock_opname_by_id(conn, opname_id)
        if not locked:
            raise NotFoundError(
                "Sesi Stock Opname tidak ditemukan.",
                details={"opname_id": opname_id},
            )
        if locked["status"] != OpnameStatus.WAITING_APPROVAL.value:
            raise InvalidStateTransition(
                f"Stock Opname berstatus '{locked['status']}' tidak dapat ditolak (harus berstatus WAITING_APPROVAL).",
                details={
                    "opname_id": opname_id,
                    "current_status": locked["status"],
                    "target_status": OpnameStatus.IN_PROGRESS.value,
                },
            )

        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))

        opname_repo.update_opname_rejected(
            conn, opname_id, rejection_reason=clean_reason
        )
        rejected = opname_repo.get_opname_by_id(conn, opname_id)
        assert rejected is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="OPNAME_REJECTED",
            entity_type=ENTITY_TYPE,
            entity_id=opname_id,
            old_values={"status": OpnameStatus.WAITING_APPROVAL.value},
            new_values={
                "status": OpnameStatus.IN_PROGRESS.value,
                "rejection_reason": clean_reason,
            },
            ip_address=ip_address,
        )
        return rejected


def cancel_stock_opname(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    opname_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """DRAFT / IN_PROGRESS -> CANCELLED (opname:manage; melepas pembekuan bila dari IN_PROGRESS; PRD 5.1, AC-10)."""
    with conn.transaction():
        locked = opname_repo.lock_opname_by_id(conn, opname_id)
        if not locked:
            raise NotFoundError(
                "Sesi Stock Opname tidak ditemukan.",
                details={"opname_id": opname_id},
            )

        current_status = str(locked["status"])
        if current_status not in CANCELLABLE_OPNAME_STATUSES:
            raise InvalidStateTransition(
                f"Stock Opname berstatus '{current_status}' tidak dapat dibatalkan (hanya DRAFT atau IN_PROGRESS yang dapat dibatalkan).",
                details={
                    "opname_id": opname_id,
                    "current_status": current_status,
                    "target_status": OpnameStatus.CANCELLED.value,
                },
            )

        access_service.ensure_warehouse_access(conn, actor, int(locked["warehouse_id"]))

        opname_repo.update_opname_cancelled(conn, opname_id)
        cancelled = opname_repo.get_opname_by_id(conn, opname_id)
        assert cancelled is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="OPNAME_CANCELLED",
            entity_type=ENTITY_TYPE,
            entity_id=opname_id,
            old_values={"status": current_status},
            new_values={"status": OpnameStatus.CANCELLED.value},
            ip_address=ip_address,
        )
        return cancelled

