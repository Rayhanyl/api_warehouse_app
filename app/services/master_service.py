"""Service logika bisnis untuk Master Data: Kategori, UoM, Pemasok, dan Barang (FR-02, PRD 6.3, 6.8)."""

import re
from typing import Any

from psycopg import Connection

from app.core.exceptions import (
    DuplicateError,
    EntityInUse,
    InactiveReferenceError,
    NotFoundError,
    ValidationDomainError,
)
from app.repositories import master_repo
from app.services import audit_service
from app.utils.pagination import build_order_by, normalize_pagination

CATEGORY_SORT_COLUMNS: dict[str, str] = {
    "id": "c.id",
    "name": "c.name",
    "created_at": "c.created_at",
}

UOM_SORT_COLUMNS: dict[str, str] = {
    "id": "u.id",
    "code": "u.code",
    "name": "u.name",
    "created_at": "u.created_at",
}

SUPPLIER_SORT_COLUMNS: dict[str, str] = {
    "id": "s.id",
    "code": "s.code",
    "name": "s.name",
    "created_at": "s.created_at",
}

ITEM_SORT_COLUMNS: dict[str, str] = {
    "id": "i.id",
    "sku": "i.sku",
    "name": "i.name",
    "created_at": "i.created_at",
}

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ============================================================================
# Categories
# ============================================================================
def list_categories(
    conn: Connection[dict[str, Any]],
    *,
    limit: int = 50,
    offset: int = 0,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=CATEGORY_SORT_COLUMNS,
        default_column="id",
        default_dir="ASC",
    )
    items, total = master_repo.list_categories(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        is_active=is_active,
        search=search,
        order_by_sql=order_by_sql,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def get_category(
    conn: Connection[dict[str, Any]], category_id: int
) -> dict[str, Any]:
    category = master_repo.get_category_by_id(conn, category_id)
    if not category:
        raise NotFoundError(
            "Kategori tidak ditemukan.",
            details={"category_id": category_id},
        )
    return category


def create_category(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    name: str,
    description: str | None = None,
    is_active: bool = True,
    ip_address: str | None = None,
) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValidationDomainError(
            "Nama kategori tidak boleh kosong.",
            details={"field": "name"},
        )
    clean_desc = description.strip() if description is not None else None

    with conn.transaction():
        existing = master_repo.get_category_by_name(conn, clean_name)
        if existing:
            raise DuplicateError(
                f"Kategori dengan nama '{clean_name}' sudah terdaftar.",
                details={"field": "name", "value": clean_name},
            )
        created = master_repo.insert_category(
            conn,
            name=clean_name,
            description=clean_desc,
            is_active=is_active,
            created_by=int(actor["id"]),
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="CATEGORY_CREATED",
            entity_type="categories",
            entity_id=created["id"],
            old_values=None,
            new_values={
                "id": created["id"],
                "name": created["name"],
                "description": created["description"],
                "is_active": created["is_active"],
            },
            ip_address=ip_address,
        )
        return created


def update_category(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    category_id: int,
    name: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    with conn.transaction():
        existing = master_repo.lock_category_by_id(conn, category_id)
        if not existing:
            raise NotFoundError(
                "Kategori tidak ditemukan.",
                details={"category_id": category_id},
            )

        new_name = existing["name"]
        if name is not None:
            new_name = name.strip()
            if not new_name:
                raise ValidationDomainError(
                    "Nama kategori tidak boleh kosong.",
                    details={"field": "name"},
                )
            if new_name.lower() != str(existing["name"]).lower():
                dup = master_repo.get_category_by_name(conn, new_name)
                if dup and int(dup["id"]) != category_id:
                    raise DuplicateError(
                        f"Kategori dengan nama '{new_name}' sudah terdaftar.",
                        details={"field": "name", "value": new_name},
                    )

        new_desc = (
            description.strip()
            if description is not None
            else existing["description"]
        )
        new_active = (
            bool(is_active) if is_active is not None else bool(existing["is_active"])
        )

        if existing["is_active"] and not new_active:
            if master_repo.is_category_in_use(conn, category_id):
                raise EntityInUse(
                    "Kategori tidak dapat dinonaktifkan karena masih dipakai oleh barang yang aktif.",
                    details={"category_id": category_id},
                )

        updated = master_repo.update_category(
            conn,
            category_id,
            name=new_name,
            description=new_desc,
            is_active=new_active,
        )
        action = (
            "CATEGORY_DEACTIVATED"
            if (existing["is_active"] and not new_active)
            else "CATEGORY_UPDATED"
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action=action,
            entity_type="categories",
            entity_id=category_id,
            old_values={
                "name": existing["name"],
                "description": existing["description"],
                "is_active": existing["is_active"],
            },
            new_values={
                "name": updated["name"],
                "description": updated["description"],
                "is_active": updated["is_active"],
            },
            ip_address=ip_address,
        )
        return updated


# ============================================================================
# Units of Measure (UoMs)
# ============================================================================
def list_uoms(
    conn: Connection[dict[str, Any]],
    *,
    limit: int = 50,
    offset: int = 0,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=UOM_SORT_COLUMNS,
        default_column="id",
        default_dir="ASC",
    )
    items, total = master_repo.list_uoms(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        is_active=is_active,
        search=search,
        order_by_sql=order_by_sql,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def get_uom(conn: Connection[dict[str, Any]], uom_id: int) -> dict[str, Any]:
    uom = master_repo.get_uom_by_id(conn, uom_id)
    if not uom:
        raise NotFoundError(
            "Satuan ukur (UoM) tidak ditemukan.",
            details={"uom_id": uom_id},
        )
    return uom


def create_uom(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    code: str,
    name: str,
    allow_decimal: bool = False,
    is_active: bool = True,
    ip_address: str | None = None,
) -> dict[str, Any]:
    clean_code = code.strip()
    clean_name = name.strip()
    if not clean_code or not clean_name:
        raise ValidationDomainError(
            "Kode dan nama UoM tidak boleh kosong.",
            details={"code": clean_code, "name": clean_name},
        )

    with conn.transaction():
        existing = master_repo.get_uom_by_code(conn, clean_code)
        if existing:
            raise DuplicateError(
                f"UoM dengan kode '{clean_code}' sudah terdaftar.",
                details={"field": "code", "value": clean_code},
            )
        created = master_repo.insert_uom(
            conn,
            code=clean_code,
            name=clean_name,
            allow_decimal=allow_decimal,
            is_active=is_active,
            created_by=int(actor["id"]),
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="UOM_CREATED",
            entity_type="uoms",
            entity_id=created["id"],
            old_values=None,
            new_values={
                "id": created["id"],
                "code": created["code"],
                "name": created["name"],
                "allow_decimal": created["allow_decimal"],
                "is_active": created["is_active"],
            },
            ip_address=ip_address,
        )
        return created


def update_uom(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    uom_id: int,
    code: str | None = None,
    name: str | None = None,
    allow_decimal: bool | None = None,
    is_active: bool | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    with conn.transaction():
        existing = master_repo.lock_uom_by_id(conn, uom_id)
        if not existing:
            raise NotFoundError(
                "Satuan ukur (UoM) tidak ditemukan.",
                details={"uom_id": uom_id},
            )

        new_code = existing["code"]
        if code is not None:
            new_code = code.strip()
            if not new_code:
                raise ValidationDomainError(
                    "Kode UoM tidak boleh kosong.",
                    details={"field": "code"},
                )
            if new_code.lower() != str(existing["code"]).lower():
                dup = master_repo.get_uom_by_code(conn, new_code)
                if dup and int(dup["id"]) != uom_id:
                    raise DuplicateError(
                        f"UoM dengan kode '{new_code}' sudah terdaftar.",
                        details={"field": "code", "value": new_code},
                    )

        new_name = existing["name"]
        if name is not None:
            new_name = name.strip()
            if not new_name:
                raise ValidationDomainError(
                    "Nama UoM tidak boleh kosong.",
                    details={"field": "name"},
                )

        new_allow_decimal = (
            bool(allow_decimal)
            if allow_decimal is not None
            else bool(existing["allow_decimal"])
        )
        new_active = (
            bool(is_active) if is_active is not None else bool(existing["is_active"])
        )

        if existing["is_active"] and not new_active:
            if master_repo.is_uom_in_use(conn, uom_id):
                raise EntityInUse(
                    "UoM tidak dapat dinonaktifkan karena masih dipakai oleh barang yang aktif.",
                    details={"uom_id": uom_id},
                )

        updated = master_repo.update_uom(
            conn,
            uom_id,
            code=new_code,
            name=new_name,
            allow_decimal=new_allow_decimal,
            is_active=new_active,
        )
        action = (
            "UOM_DEACTIVATED"
            if (existing["is_active"] and not new_active)
            else "UOM_UPDATED"
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action=action,
            entity_type="uoms",
            entity_id=uom_id,
            old_values={
                "code": existing["code"],
                "name": existing["name"],
                "allow_decimal": existing["allow_decimal"],
                "is_active": existing["is_active"],
            },
            new_values={
                "code": updated["code"],
                "name": updated["name"],
                "allow_decimal": updated["allow_decimal"],
                "is_active": updated["is_active"],
            },
            ip_address=ip_address,
        )
        return updated


# ============================================================================
# Suppliers
# ============================================================================
def list_suppliers(
    conn: Connection[dict[str, Any]],
    *,
    limit: int = 50,
    offset: int = 0,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=SUPPLIER_SORT_COLUMNS,
        default_column="id",
        default_dir="ASC",
    )
    items, total = master_repo.list_suppliers(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        is_active=is_active,
        search=search,
        order_by_sql=order_by_sql,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def get_supplier(
    conn: Connection[dict[str, Any]], supplier_id: int
) -> dict[str, Any]:
    supplier = master_repo.get_supplier_by_id(conn, supplier_id)
    if not supplier:
        raise NotFoundError(
            "Pemasok tidak ditemukan.",
            details={"supplier_id": supplier_id},
        )
    return supplier


def create_supplier(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    code: str,
    name: str,
    contact_person: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    is_active: bool = True,
    ip_address: str | None = None,
) -> dict[str, Any]:
    clean_code = code.strip()
    clean_name = name.strip()
    if not clean_code or not clean_name:
        raise ValidationDomainError(
            "Kode dan nama pemasok tidak boleh kosong.",
            details={"code": clean_code, "name": clean_name},
        )

    clean_email: str | None = None
    if email is not None and email.strip():
        clean_email = email.strip().lower()
        if not EMAIL_REGEX.match(clean_email):
            raise ValidationDomainError(
                "Format alamat email pemasok tidak valid.",
                details={"field": "email", "value": clean_email},
            )

    with conn.transaction():
        existing = master_repo.get_supplier_by_code(conn, clean_code)
        if existing:
            raise DuplicateError(
                f"Pemasok dengan kode '{clean_code}' sudah terdaftar.",
                details={"field": "code", "value": clean_code},
            )
        created = master_repo.insert_supplier(
            conn,
            code=clean_code,
            name=clean_name,
            contact_person=contact_person.strip() if contact_person else None,
            phone=phone.strip() if phone else None,
            email=clean_email,
            address=address.strip() if address else None,
            is_active=is_active,
            created_by=int(actor["id"]),
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="SUPPLIER_CREATED",
            entity_type="suppliers",
            entity_id=created["id"],
            old_values=None,
            new_values={
                "id": created["id"],
                "code": created["code"],
                "name": created["name"],
                "contact_person": created["contact_person"],
                "phone": created["phone"],
                "email": created["email"],
                "address": created["address"],
                "is_active": created["is_active"],
            },
            ip_address=ip_address,
        )
        return created


def update_supplier(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    supplier_id: int,
    code: str | None = None,
    name: str | None = None,
    contact_person: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    is_active: bool | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    with conn.transaction():
        existing = master_repo.lock_supplier_by_id(conn, supplier_id)
        if not existing:
            raise NotFoundError(
                "Pemasok tidak ditemukan.",
                details={"supplier_id": supplier_id},
            )

        new_code = existing["code"]
        if code is not None:
            new_code = code.strip()
            if not new_code:
                raise ValidationDomainError(
                    "Kode pemasok tidak boleh kosong.",
                    details={"field": "code"},
                )
            if new_code.lower() != str(existing["code"]).lower():
                dup = master_repo.get_supplier_by_code(conn, new_code)
                if dup and int(dup["id"]) != supplier_id:
                    raise DuplicateError(
                        f"Pemasok dengan kode '{new_code}' sudah terdaftar.",
                        details={"field": "code", "value": new_code},
                    )

        new_name = existing["name"]
        if name is not None:
            new_name = name.strip()
            if not new_name:
                raise ValidationDomainError(
                    "Nama pemasok tidak boleh kosong.",
                    details={"field": "name"},
                )

        new_contact = (
            contact_person.strip()
            if contact_person is not None
            else existing["contact_person"]
        )
        new_phone = phone.strip() if phone is not None else existing["phone"]
        new_address = address.strip() if address is not None else existing["address"]

        new_email = existing["email"]
        if email is not None:
            new_email = email.strip().lower() if email.strip() else None
            if new_email and not EMAIL_REGEX.match(new_email):
                raise ValidationDomainError(
                    "Format alamat email pemasok tidak valid.",
                    details={"field": "email", "value": new_email},
                )

        new_active = (
            bool(is_active) if is_active is not None else bool(existing["is_active"])
        )

        # PRD 6.8: Pemasok tidak dapat dinonaktifkan jika masih memiliki PO yang belum final
        if existing["is_active"] and not new_active:
            if master_repo.is_supplier_in_use(conn, supplier_id):
                raise EntityInUse(
                    "Pemasok tidak dapat dinonaktifkan karena masih memiliki Purchase Order yang belum final.",
                    details={"supplier_id": supplier_id},
                )

        updated = master_repo.update_supplier(
            conn,
            supplier_id,
            code=new_code,
            name=new_name,
            contact_person=new_contact,
            phone=new_phone,
            email=new_email,
            address=new_address,
            is_active=new_active,
        )
        action = (
            "SUPPLIER_DEACTIVATED"
            if (existing["is_active"] and not new_active)
            else "SUPPLIER_UPDATED"
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action=action,
            entity_type="suppliers",
            entity_id=supplier_id,
            old_values={
                "code": existing["code"],
                "name": existing["name"],
                "contact_person": existing["contact_person"],
                "phone": existing["phone"],
                "email": existing["email"],
                "address": existing["address"],
                "is_active": existing["is_active"],
            },
            new_values={
                "code": updated["code"],
                "name": updated["name"],
                "contact_person": updated["contact_person"],
                "phone": updated["phone"],
                "email": updated["email"],
                "address": updated["address"],
                "is_active": updated["is_active"],
            },
            ip_address=ip_address,
        )
        return updated


# ============================================================================
# Items
# ============================================================================
def list_items(
    conn: Connection[dict[str, Any]],
    *,
    limit: int = 50,
    offset: int = 0,
    category_id: int | None = None,
    uom_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=ITEM_SORT_COLUMNS,
        default_column="id",
        default_dir="ASC",
    )
    items, total = master_repo.list_items(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        category_id=category_id,
        uom_id=uom_id,
        is_active=is_active,
        search=search,
        order_by_sql=order_by_sql,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def get_item(conn: Connection[dict[str, Any]], item_id: int) -> dict[str, Any]:
    item = master_repo.get_item_by_id(conn, item_id)
    if not item:
        raise NotFoundError(
            "Barang tidak ditemukan.",
            details={"item_id": item_id},
        )
    return item


def create_item(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    sku: str,
    name: str,
    description: str | None = None,
    category_id: int,
    uom_id: int,
    is_active: bool = True,
    ip_address: str | None = None,
) -> dict[str, Any]:
    clean_sku = sku.strip()
    clean_name = name.strip()
    if not clean_sku or not clean_name:
        raise ValidationDomainError(
            "SKU dan nama barang tidak boleh kosong.",
            details={"sku": clean_sku, "name": clean_name},
        )

    with conn.transaction():
        existing = master_repo.get_item_by_sku(conn, clean_sku)
        if existing:
            raise DuplicateError(
                f"Barang dengan SKU '{clean_sku}' sudah terdaftar.",
                details={"field": "sku", "value": clean_sku},
            )

        category = master_repo.get_category_by_id(conn, category_id)
        if not category:
            raise NotFoundError(
                "Kategori tidak ditemukan.",
                details={"category_id": category_id},
            )
        if not category["is_active"]:
            raise InactiveReferenceError(
                "Kategori yang dipilih berstatus tidak aktif.",
                details={"category_id": category_id},
            )

        uom = master_repo.get_uom_by_id(conn, uom_id)
        if not uom:
            raise NotFoundError(
                "Satuan ukur (UoM) tidak ditemukan.",
                details={"uom_id": uom_id},
            )
        if not uom["is_active"]:
            raise InactiveReferenceError(
                "Satuan ukur (UoM) yang dipilih berstatus tidak aktif.",
                details={"uom_id": uom_id},
            )

        created = master_repo.insert_item(
            conn,
            sku=clean_sku,
            name=clean_name,
            description=description.strip() if description is not None else None,
            category_id=category_id,
            uom_id=uom_id,
            is_active=is_active,
            created_by=int(actor["id"]),
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="ITEM_CREATED",
            entity_type="items",
            entity_id=created["id"],
            old_values=None,
            new_values={
                "id": created["id"],
                "sku": created["sku"],
                "name": created["name"],
                "description": created["description"],
                "category_id": created["category_id"],
                "uom_id": created["uom_id"],
                "is_active": created["is_active"],
            },
            ip_address=ip_address,
        )
        return created


def update_item(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    item_id: int,
    sku: str | None = None,
    name: str | None = None,
    description: str | None = None,
    category_id: int | None = None,
    uom_id: int | None = None,
    is_active: bool | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    with conn.transaction():
        existing = master_repo.lock_item_by_id(conn, item_id)
        if not existing:
            raise NotFoundError(
                "Barang tidak ditemukan.",
                details={"item_id": item_id},
            )

        new_sku = existing["sku"]
        if sku is not None:
            new_sku = sku.strip()
            if not new_sku:
                raise ValidationDomainError(
                    "SKU barang tidak boleh kosong.",
                    details={"field": "sku"},
                )
            if new_sku != existing["sku"]:
                # PRD FR-02 & 6.8: SKU tidak dapat diubah setelah barang dipakai pada transaksi apa pun
                if master_repo.is_item_used_in_transactions(conn, item_id):
                    raise EntityInUse(
                        "SKU barang tidak dapat diubah setelah barang dipakai pada transaksi.",
                        details={"item_id": item_id, "sku": existing["sku"]},
                    )
                dup = master_repo.get_item_by_sku(conn, new_sku)
                if dup and int(dup["id"]) != item_id:
                    raise DuplicateError(
                        f"Barang dengan SKU '{new_sku}' sudah terdaftar.",
                        details={"field": "sku", "value": new_sku},
                    )

        new_name = existing["name"]
        if name is not None:
            new_name = name.strip()
            if not new_name:
                raise ValidationDomainError(
                    "Nama barang tidak boleh kosong.",
                    details={"field": "name"},
                )

        new_desc = (
            description.strip()
            if description is not None
            else existing["description"]
        )

        new_category_id = int(existing["category_id"])
        if category_id is not None and int(category_id) != new_category_id:
            cat = master_repo.get_category_by_id(conn, category_id)
            if not cat:
                raise NotFoundError(
                    "Kategori tidak ditemukan.",
                    details={"category_id": category_id},
                )
            if not cat["is_active"]:
                raise InactiveReferenceError(
                    "Kategori yang dipilih berstatus tidak aktif.",
                    details={"category_id": category_id},
                )
            new_category_id = int(category_id)

        new_uom_id = int(existing["uom_id"])
        if uom_id is not None and int(uom_id) != new_uom_id:
            if master_repo.is_item_used_in_transactions(conn, item_id):
                raise EntityInUse(
                    "Satuan ukur (UoM) dasar barang tidak dapat diubah setelah barang dipakai pada transaksi.",
                    details={"item_id": item_id, "uom_id": existing["uom_id"]},
                )
            uom = master_repo.get_uom_by_id(conn, uom_id)
            if not uom:
                raise NotFoundError(
                    "Satuan ukur (UoM) tidak ditemukan.",
                    details={"uom_id": uom_id},
                )
            if not uom["is_active"]:
                raise InactiveReferenceError(
                    "Satuan ukur (UoM) yang dipilih berstatus tidak aktif.",
                    details={"uom_id": uom_id},
                )
            new_uom_id = int(uom_id)

        new_active = (
            bool(is_active) if is_active is not None else bool(existing["is_active"])
        )

        # PRD 6.8: Barang tidak dapat dinonaktifkan jika masih memiliki saldo != 0 atau ada di dokumen belum final
        if existing["is_active"] and not new_active:
            if master_repo.is_item_in_use(conn, item_id):
                raise EntityInUse(
                    "Barang tidak dapat dinonaktifkan karena masih memiliki saldo stok atau dipakai pada dokumen yang belum final.",
                    details={"item_id": item_id},
                )

        updated = master_repo.update_item(
            conn,
            item_id,
            sku=new_sku,
            name=new_name,
            description=new_desc,
            category_id=new_category_id,
            uom_id=new_uom_id,
            is_active=new_active,
        )
        action = (
            "ITEM_DEACTIVATED"
            if (existing["is_active"] and not new_active)
            else "ITEM_UPDATED"
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action=action,
            entity_type="items",
            entity_id=item_id,
            old_values={
                "sku": existing["sku"],
                "name": existing["name"],
                "description": existing["description"],
                "category_id": existing["category_id"],
                "uom_id": existing["uom_id"],
                "is_active": existing["is_active"],
            },
            new_values={
                "sku": updated["sku"],
                "name": updated["name"],
                "description": updated["description"],
                "category_id": updated["category_id"],
                "uom_id": updated["uom_id"],
                "is_active": updated["is_active"],
            },
            ip_address=ip_address,
        )
        return updated

