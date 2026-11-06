"""Service logika bisnis untuk Gudang (warehouses) dan Lokasi Penyimpanan (storage_locations) (FR-02, PRD 3.2, 6.3, 6.8)."""

import re
from typing import Any

from psycopg import Connection

from app.core.exceptions import (
    DuplicateError,
    EntityInUse,
    InactiveReferenceError,
    InvalidLocationError,
    NotFoundError,
    ValidationDomainError,
)
from app.repositories import warehouse_repo
from app.services import access_service, audit_service
from app.utils.pagination import build_order_by, normalize_pagination

CODE_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

# Nilai parameter `purpose` untuk referensi gudang/lokasi tujuan Stock Transfer (PRD 3.2 poin 2).
PURPOSE_TRANSFER_DESTINATION = "transfer_destination"
ALLOWED_PURPOSES: frozenset[str] = frozenset({PURPOSE_TRANSFER_DESTINATION})


def _resolve_reference_scope(
    conn: Connection[dict[str, Any]],
    actor: dict[str, Any],
    *,
    purpose: str | None,
    is_active: bool | None,
) -> tuple[list[int] | None, bool | None, bool]:
    """Menentukan cakupan baca gudang/lokasi (PRD 3.2 poin 2).

    Mengembalikan (scoped_warehouse_ids, is_active efektif, mode_tujuan_transfer).
    - Tanpa `purpose`: peran ber-scope hanya melihat gudang pada user_warehouses.
    - `purpose=transfer_destination`: gudang/lokasi aktif lintas gudang untuk dipilih
      sebagai tujuan Stock Transfer.
    """
    if purpose is None:
        return access_service.get_scoped_warehouse_ids_for_read(conn, actor), is_active, False

    clean_purpose = purpose.strip().lower()
    if clean_purpose not in ALLOWED_PURPOSES:
        raise ValidationDomainError(
            f"Nilai parameter purpose '{purpose}' tidak valid.",
            details={"field": "purpose", "value": purpose, "allowed_values": sorted(ALLOWED_PURPOSES)},
        )
    if is_active is False:
        raise ValidationDomainError(
            "Parameter purpose=transfer_destination hanya mengembalikan data aktif; is_active=false tidak dapat digunakan bersamaan.",
            details={"field": "is_active", "purpose": clean_purpose},
        )
    return None, True, True


def _validate_code_format(value: str, *, field_name: str, label: str) -> str:
    clean = value.strip()
    if not clean:
        raise ValidationDomainError(
            f"{label} tidak boleh kosong.",
            details={"field": field_name},
        )
    if not CODE_REGEX.match(clean):
        raise ValidationDomainError(
            f"Format {label.lower()} tidak valid; hanya boleh diawali huruf/angka dan berisi huruf, angka, titik (.), garis bawah (_), garis miring (/), atau tanda hubung (-) tanpa spasi.",
            details={"field": field_name, "value": clean},
        )
    return clean

WAREHOUSE_SORT_COLUMNS: dict[str, str] = {
    "id": "w.id",
    "code": "w.code",
    "name": "w.name",
    "created_at": "w.created_at",
}

LOCATION_SORT_COLUMNS: dict[str, str] = {
    "id": "sl.id",
    "code": "sl.code",
    "name": "sl.name",
    "warehouse_id": "sl.warehouse_id",
    "created_at": "sl.created_at",
}


# ============================================================================
# Warehouses
# ============================================================================
def list_warehouses(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    purpose: str | None = None,
) -> dict[str, Any]:
    scoped_ids, effective_is_active, _ = _resolve_reference_scope(
        conn, actor, purpose=purpose, is_active=is_active
    )
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=WAREHOUSE_SORT_COLUMNS,
        default_column="id",
        default_dir="ASC",
    )
    items, total = warehouse_repo.list_warehouses(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        is_active=effective_is_active,
        search=search,
        order_by_sql=order_by_sql,
        scoped_warehouse_ids=scoped_ids,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def get_warehouse(
    conn: Connection[dict[str, Any]],
    warehouse_id: int,
    *,
    actor: dict[str, Any],
) -> dict[str, Any]:
    warehouse = warehouse_repo.get_warehouse_by_id(conn, warehouse_id)
    if not warehouse:
        raise NotFoundError(
            "Gudang tidak ditemukan.",
            details={"warehouse_id": warehouse_id},
        )
    access_service.ensure_warehouse_read_access(conn, actor, warehouse_id)
    return warehouse


def create_warehouse(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    code: str,
    name: str,
    address: str | None = None,
    allow_negative_stock: bool = False,
    is_active: bool = True,
    ip_address: str | None = None,
) -> dict[str, Any]:
    clean_code = code.strip()
    clean_name = name.strip()
    if not clean_code or not clean_name:
        raise ValidationDomainError(
            "Kode dan nama gudang tidak boleh kosong.",
            details={"code": clean_code, "name": clean_name},
        )
    clean_code = _validate_code_format(
        clean_code, field_name="code", label="Kode gudang"
    )

    with conn.transaction():
        existing = warehouse_repo.get_warehouse_by_code(conn, clean_code)
        if existing:
            raise DuplicateError(
                f"Gudang dengan kode '{clean_code}' sudah terdaftar.",
                details={"field": "code", "value": clean_code},
            )
        created = warehouse_repo.insert_warehouse(
            conn,
            code=clean_code,
            name=clean_name,
            address=address.strip() if address is not None else None,
            allow_negative_stock=allow_negative_stock,
            is_active=is_active,
            created_by=int(actor["id"]),
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="WAREHOUSE_CREATED",
            entity_type="warehouses",
            entity_id=created["id"],
            old_values=None,
            new_values={
                "id": created["id"],
                "code": created["code"],
                "name": created["name"],
                "address": created["address"],
                "allow_negative_stock": created["allow_negative_stock"],
                "is_active": created["is_active"],
            },
            ip_address=ip_address,
        )
        return created


def update_warehouse(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    warehouse_id: int,
    code: str | None = None,
    name: str | None = None,
    address: str | None = None,
    allow_negative_stock: bool | None = None,
    is_active: bool | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    with conn.transaction():
        existing = warehouse_repo.lock_warehouse_by_id(conn, warehouse_id)
        if not existing:
            raise NotFoundError(
                "Gudang tidak ditemukan.",
                details={"warehouse_id": warehouse_id},
            )

        new_code = existing["code"]
        if code is not None:
            new_code = _validate_code_format(
                code, field_name="code", label="Kode gudang"
            )
            if new_code.lower() != str(existing["code"]).lower():
                dup = warehouse_repo.get_warehouse_by_code(conn, new_code)
                if dup and int(dup["id"]) != warehouse_id:
                    raise DuplicateError(
                        f"Gudang dengan kode '{new_code}' sudah terdaftar.",
                        details={"field": "code", "value": new_code},
                    )

        new_name = existing["name"]
        if name is not None:
            new_name = name.strip()
            if not new_name:
                raise ValidationDomainError(
                    "Nama gudang tidak boleh kosong.",
                    details={"field": "name"},
                )

        new_address = (
            address.strip() if address is not None else existing["address"]
        )
        new_allow_neg = (
            bool(allow_negative_stock)
            if allow_negative_stock is not None
            else bool(existing["allow_negative_stock"])
        )
        new_active = (
            bool(is_active) if is_active is not None else bool(existing["is_active"])
        )

        # PRD 6.8: Gudang tidak dapat dinonaktifkan jika masih memiliki saldo != 0 atau ada di dokumen belum final
        if existing["is_active"] and not new_active:
            if warehouse_repo.is_warehouse_in_use(conn, warehouse_id):
                raise EntityInUse(
                    "Gudang tidak dapat dinonaktifkan karena masih memiliki saldo stok atau dipakai pada dokumen yang belum final.",
                    details={"warehouse_id": warehouse_id},
                )

        updated = warehouse_repo.update_warehouse(
            conn,
            warehouse_id,
            code=new_code,
            name=new_name,
            address=new_address,
            allow_negative_stock=new_allow_neg,
            is_active=new_active,
        )
        action = (
            "WAREHOUSE_DEACTIVATED"
            if (existing["is_active"] and not new_active)
            else "WAREHOUSE_UPDATED"
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action=action,
            entity_type="warehouses",
            entity_id=warehouse_id,
            old_values={
                "code": existing["code"],
                "name": existing["name"],
                "address": existing["address"],
                "allow_negative_stock": existing["allow_negative_stock"],
                "is_active": existing["is_active"],
            },
            new_values={
                "code": updated["code"],
                "name": updated["name"],
                "address": updated["address"],
                "allow_negative_stock": updated["allow_negative_stock"],
                "is_active": updated["is_active"],
            },
            ip_address=ip_address,
        )
        return updated


# ============================================================================
# Storage Locations
# ============================================================================
def list_locations(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    warehouse_id: int | None = None,
    require_warehouse_exists: bool = False,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    purpose: str | None = None,
) -> dict[str, Any]:
    scoped_ids, effective_is_active, is_dest = _resolve_reference_scope(
        conn, actor, purpose=purpose, is_active=is_active
    )

    if warehouse_id is not None:
        if is_dest:
            wh = warehouse_repo.get_warehouse_by_id(conn, warehouse_id)
            if not wh or not wh["is_active"]:
                raise InactiveReferenceError(
                    "Gudang tujuan transfer tidak ditemukan atau tidak aktif.",
                    details={"warehouse_id": warehouse_id},
                )
        else:
            if require_warehouse_exists:
                wh = warehouse_repo.get_warehouse_by_id(conn, warehouse_id)
                if not wh:
                    raise NotFoundError(
                        "Gudang tidak ditemukan.",
                        details={"warehouse_id": warehouse_id},
                    )
            access_service.ensure_warehouse_read_access(conn, actor, warehouse_id)

    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=LOCATION_SORT_COLUMNS,
        default_column="id",
        default_dir="ASC",
    )
    items, total = warehouse_repo.list_locations(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        warehouse_id=warehouse_id,
        is_active=effective_is_active,
        search=search,
        order_by_sql=order_by_sql,
        scoped_warehouse_ids=scoped_ids,
        require_active_warehouse=is_dest,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def get_location(
    conn: Connection[dict[str, Any]],
    location_id: int,
    *,
    actor: dict[str, Any],
) -> dict[str, Any]:
    location = warehouse_repo.get_location_by_id(conn, location_id)
    if not location:
        raise NotFoundError(
            "Lokasi penyimpanan tidak ditemukan.",
            details={"location_id": location_id},
        )
    access_service.ensure_warehouse_read_access(
        conn, actor, int(location["warehouse_id"])
    )
    return location


def validate_location(
    conn: Connection[dict[str, Any]],
    *,
    warehouse_id: int,
    location_id: int,
) -> dict[str, Any]:
    """Contract WHS (`validate_location`): memastikan gudang aktif dan lokasi aktif serta milik gudang tersebut (PRD 4.3, 6.5)."""
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

    location = warehouse_repo.get_location_by_id(conn, location_id)
    if not location or int(location["warehouse_id"]) != int(warehouse_id):
        raise InvalidLocationError(
            "Lokasi penyimpanan tidak ditemukan atau bukan milik gudang yang direferensikan.",
            details={"warehouse_id": warehouse_id, "location_id": location_id},
        )
    if not location["is_active"]:
        raise InvalidLocationError(
            f"Lokasi penyimpanan '{location['code']}' berstatus tidak aktif.",
            details={"warehouse_id": warehouse_id, "location_id": location_id},
        )
    return location


def create_location(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    warehouse_id: int,
    code: str,
    name: str,
    is_active: bool = True,
    ip_address: str | None = None,
) -> dict[str, Any]:
    clean_code = code.strip()
    clean_name = name.strip()
    if not clean_code or not clean_name:
        raise ValidationDomainError(
            "Kode dan nama lokasi penyimpanan tidak boleh kosong.",
            details={"code": clean_code, "name": clean_name},
        )
    clean_code = _validate_code_format(
        clean_code, field_name="code", label="Kode lokasi penyimpanan"
    )

    with conn.transaction():
        warehouse = warehouse_repo.get_warehouse_by_id(conn, warehouse_id)
        if not warehouse:
            raise NotFoundError(
                "Gudang tidak ditemukan.",
                details={"warehouse_id": warehouse_id},
            )

        # PRD Matriks 3.1 & 3.2: location:manage bertanda (g) -> wajib ditugaskan ke gudang terkait
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        if not warehouse["is_active"]:
            raise InactiveReferenceError(
                "Gudang tujuan lokasi penyimpanan berstatus tidak aktif.",
                details={"warehouse_id": warehouse_id},
            )

        existing = warehouse_repo.get_location_by_warehouse_and_code(
            conn, warehouse_id, clean_code
        )
        if existing:
            raise DuplicateError(
                f"Lokasi dengan kode '{clean_code}' sudah terdaftar pada gudang ini.",
                details={"warehouse_id": warehouse_id, "code": clean_code},
            )

        created = warehouse_repo.insert_location(
            conn,
            warehouse_id=warehouse_id,
            code=clean_code,
            name=clean_name,
            is_active=is_active,
            created_by=int(actor["id"]),
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="LOCATION_CREATED",
            entity_type="storage_locations",
            entity_id=created["id"],
            old_values=None,
            new_values={
                "id": created["id"],
                "warehouse_id": created["warehouse_id"],
                "code": created["code"],
                "name": created["name"],
                "is_active": created["is_active"],
            },
            ip_address=ip_address,
        )
        return created


def update_location(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    location_id: int,
    code: str | None = None,
    name: str | None = None,
    is_active: bool | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    with conn.transaction():
        existing = warehouse_repo.lock_location_by_id(conn, location_id)
        if not existing:
            raise NotFoundError(
                "Lokasi penyimpanan tidak ditemukan.",
                details={"location_id": location_id},
            )

        warehouse_id = int(existing["warehouse_id"])
        # PRD Matriks 3.1 & 3.2: location:manage bertanda (g) -> wajib ditugaskan ke gudang terkait
        access_service.ensure_warehouse_access(conn, actor, warehouse_id)

        new_code = existing["code"]
        if code is not None:
            new_code = _validate_code_format(
                code, field_name="code", label="Kode lokasi penyimpanan"
            )
            if new_code.lower() != str(existing["code"]).lower():
                dup = warehouse_repo.get_location_by_warehouse_and_code(
                    conn, warehouse_id, new_code
                )
                if dup and int(dup["id"]) != location_id:
                    raise DuplicateError(
                        f"Lokasi dengan kode '{new_code}' sudah terdaftar pada gudang ini.",
                        details={"warehouse_id": warehouse_id, "code": new_code},
                    )

        new_name = existing["name"]
        if name is not None:
            new_name = name.strip()
            if not new_name:
                raise ValidationDomainError(
                    "Nama lokasi penyimpanan tidak boleh kosong.",
                    details={"field": "name"},
                )

        new_active = (
            bool(is_active) if is_active is not None else bool(existing["is_active"])
        )

        # PRD 6.8: Lokasi tidak dapat dinonaktifkan jika masih memiliki saldo != 0 atau ada di dokumen belum final
        if existing["is_active"] and not new_active:
            if warehouse_repo.is_location_in_use(conn, location_id, warehouse_id):
                raise EntityInUse(
                    "Lokasi penyimpanan tidak dapat dinonaktifkan karena masih memiliki saldo stok atau dipakai pada dokumen yang belum final.",
                    details={"location_id": location_id, "warehouse_id": warehouse_id},
                )

        updated = warehouse_repo.update_location(
            conn,
            location_id,
            code=new_code,
            name=new_name,
            is_active=new_active,
        )
        action = (
            "LOCATION_DEACTIVATED"
            if (existing["is_active"] and not new_active)
            else "LOCATION_UPDATED"
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action=action,
            entity_type="storage_locations",
            entity_id=location_id,
            old_values={
                "warehouse_id": warehouse_id,
                "code": existing["code"],
                "name": existing["name"],
                "is_active": existing["is_active"],
            },
            new_values={
                "warehouse_id": warehouse_id,
                "code": updated["code"],
                "name": updated["name"],
                "is_active": updated["is_active"],
            },
            ip_address=ip_address,
        )
        return updated

