"""Service logika bisnis untuk Master Data: Kategori, UoM, Pemasok, dan Barang (FR-02, PRD 6.3, 6.8)."""

import re
from collections import Counter
from io import BytesIO
from typing import Any
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.utils.exceptions import InvalidFileException
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
CODE_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
PHONE_REGEX = re.compile(r"^[0-9+() -]{6,30}$")
ITEM_IMPORT_HEADERS = (
    "sku",
    "name",
    "description",
    "category_name",
    "uom_name",
    "is_active",
)
ITEM_IMPORT_REFERENCE_HEADERS = ("category_name", "uom_name", "uom_code")
ITEM_IMPORT_MAX_BYTES = 5 * 1024 * 1024
ITEM_IMPORT_MAX_ROWS = 1000
SUPPLIER_IMPORT_HEADERS = (
    "code",
    "name",
    "contact_person",
    "phone",
    "email",
    "address",
    "is_active",
)
SUPPLIER_IMPORT_MAX_BYTES = 5 * 1024 * 1024
SUPPLIER_IMPORT_MAX_ROWS = 1000


def _item_import_error(
    row: int, field: str, code: str, message: str
) -> dict[str, Any]:
    return {"row": row, "field": field, "code": code, "message": message}


def _item_import_cell_is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def build_item_import_template(conn: Connection[dict[str, Any]]) -> bytes:
    """Membuat template Excel sesuai kontrak MST-F06."""
    with conn.transaction():
        categories = master_repo.list_active_item_import_categories(conn)
        uoms = master_repo.list_active_item_import_uoms(conn)

    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "Items"
    worksheet.append(ITEM_IMPORT_HEADERS)
    for column, width in {
        "A": 18,
        "B": 30,
        "C": 40,
        "D": 24,
        "E": 24,
        "F": 14,
    }.items():
        worksheet.column_dimensions[column].width = width
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:F{ITEM_IMPORT_MAX_ROWS + 1}"
    for row_number in range(2, ITEM_IMPORT_MAX_ROWS + 2):
        for column_number in range(1, len(ITEM_IMPORT_HEADERS)):
            worksheet.cell(row=row_number, column=column_number).number_format = "@"

    reference_sheet = workbook.create_sheet("Referensi")
    reference_sheet.append(ITEM_IMPORT_REFERENCE_HEADERS)
    reference_sheet.column_dimensions["A"].width = 30
    reference_sheet.column_dimensions["B"].width = 30
    reference_sheet.column_dimensions["C"].width = 20
    reference_sheet.freeze_panes = "A2"
    reference_sheet.auto_filter.ref = (
        f"A1:C{max(len(categories), len(uoms)) + 1}"
    )
    for index in range(max(len(categories), len(uoms))):
        category_name = categories[index]["name"] if index < len(categories) else None
        uom = uoms[index] if index < len(uoms) else None
        reference_sheet.append(
            [category_name, uom["name"] if uom else None, uom["code"] if uom else None]
        )
        for column_number in range(1, 4):
            reference_sheet.cell(row=index + 2, column=column_number).number_format = "@"

    category_end = max(len(categories) + 1, 2)
    uom_end = max(len(uoms) + 1, 2)
    workbook.defined_names.add(
        DefinedName(
            "ActiveCategories",
            attr_text=f"'Referensi'!$A$2:$A${category_end}",
        )
    )
    workbook.defined_names.add(
        DefinedName(
            "ActiveUomNames",
            attr_text=f"'Referensi'!$B$2:$B${uom_end}",
        )
    )
    category_validation = DataValidation(
        type="list", formula1="=ActiveCategories", allow_blank=False
    )
    category_validation.error = "Pilih kategori dari sheet Referensi."
    category_validation.errorTitle = "Kategori tidak tersedia"
    category_validation.showErrorMessage = True
    worksheet.add_data_validation(category_validation)
    category_validation.add(f"D2:D{ITEM_IMPORT_MAX_ROWS + 1}")

    uom_validation = DataValidation(
        type="list", formula1="=ActiveUomNames", allow_blank=False
    )
    uom_validation.error = "Pilih satuan dari sheet Referensi."
    uom_validation.errorTitle = "Satuan tidak tersedia"
    uom_validation.showErrorMessage = True
    worksheet.add_data_validation(uom_validation)
    uom_validation.add(f"E2:E{ITEM_IMPORT_MAX_ROWS + 1}")

    active_validation = DataValidation(
        type="list", formula1='"active,inactive"', allow_blank=True
    )
    active_validation.showErrorMessage = True
    worksheet.add_data_validation(active_validation)
    active_validation.add(f"F2:F{ITEM_IMPORT_MAX_ROWS + 1}")
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def build_supplier_import_template() -> bytes:
    """Membuat template Excel supplier sesuai batas dan schema master data."""
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "Suppliers"
    worksheet.append(SUPPLIER_IMPORT_HEADERS)
    for column, width in {
        "A": 20,
        "B": 32,
        "C": 28,
        "D": 20,
        "E": 34,
        "F": 44,
        "G": 16,
    }.items():
        worksheet.column_dimensions[column].width = width
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:G{SUPPLIER_IMPORT_MAX_ROWS + 1}"
    for row_number in range(2, SUPPLIER_IMPORT_MAX_ROWS + 2):
        for column_number in range(1, len(SUPPLIER_IMPORT_HEADERS)):
            worksheet.cell(row=row_number, column=column_number).number_format = "@"

    active_validation = DataValidation(
        type="list", formula1='"active,inactive"', allow_blank=True
    )
    active_validation.showErrorMessage = True
    worksheet.add_data_validation(active_validation)
    active_validation.add(f"G2:G{SUPPLIER_IMPORT_MAX_ROWS + 1}")

    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def _parse_item_import_workbook(file_bytes: bytes) -> list[dict[str, Any]]:
    if not file_bytes or len(file_bytes) > ITEM_IMPORT_MAX_BYTES:
        raise ValidationDomainError(
            "Ukuran file Excel tidak valid atau melebihi batas 5 MiB.",
            details={"field": "file"},
        )

    try:
        workbook = load_workbook(
            BytesIO(file_bytes), read_only=True, data_only=False
        )
    except (BadZipFile, InvalidFileException, OSError, ParseError, ValueError, KeyError) as exc:
        raise ValidationDomainError(
            "File tidak dapat dibaca sebagai workbook Excel (.xlsx).",
            details={"field": "file"},
        ) from exc

    try:
        if workbook.sheetnames != ["Items", "Referensi"]:
            raise ValidationDomainError(
                "Workbook harus memiliki sheet 'Items' dan 'Referensi'.",
                details={"field": "file"},
            )

        worksheet = workbook["Items"]
        reference_sheet = workbook["Referensi"]
        if (
            (reference_sheet.max_column or 0) > len(ITEM_IMPORT_REFERENCE_HEADERS)
            or tuple(
                cell.value
                for cell in next(
                    reference_sheet.iter_rows(
                        min_row=1,
                        max_row=1,
                        max_col=len(ITEM_IMPORT_REFERENCE_HEADERS),
                    ),
                    (),
                )
            )
            != ITEM_IMPORT_REFERENCE_HEADERS
        ):
            raise ValidationDomainError(
                "Header sheet Referensi tidak sesuai template.",
                details={"field": "file"},
            )
        if (worksheet.max_column or 0) > len(ITEM_IMPORT_HEADERS):
            raise ValidationDomainError(
                "Workbook tidak boleh memiliki kolom di luar template.",
                details={"field": "file"},
            )
        max_column = len(ITEM_IMPORT_HEADERS)
        header_cells = next(
            worksheet.iter_rows(min_row=1, max_row=1, max_col=max_column),
            (),
        )
        actual_headers = [cell.value for cell in header_cells[: len(ITEM_IMPORT_HEADERS)]]
        extra_headers = header_cells[len(ITEM_IMPORT_HEADERS) :]
        if actual_headers != list(ITEM_IMPORT_HEADERS) or any(
            not _item_import_cell_is_blank(cell.value) for cell in extra_headers
        ):
            raise ValidationDomainError(
                "Header workbook tidak sesuai template import barang.",
                details={"field": "file"},
            )

        records: list[dict[str, Any]] = []
        for row_number, cells in enumerate(
            worksheet.iter_rows(min_row=2, max_col=max_column), start=2
        ):
            values = [cell.value for cell in cells]
            if all(_item_import_cell_is_blank(value) for value in values):
                continue
            if len(records) >= ITEM_IMPORT_MAX_ROWS:
                raise ValidationDomainError(
                    "Workbook melebihi batas 1.000 baris data.",
                    details={"field": "file"},
                )

            errors: list[dict[str, Any]] = []
            for index, cell in enumerate(cells[len(ITEM_IMPORT_HEADERS) :], start=len(ITEM_IMPORT_HEADERS)):
                if not _item_import_cell_is_blank(cell.value):
                    errors.append(
                        _item_import_error(
                            row_number,
                            "row",
                            ValidationDomainError.code,
                            "Baris berisi nilai di luar kolom template.",
                        )
                    )
                    break

            row_cells = cells[: len(ITEM_IMPORT_HEADERS)]
            for index, cell in enumerate(row_cells):
                if cell.data_type == "f":
                    errors.append(
                        _item_import_error(
                            row_number,
                            ITEM_IMPORT_HEADERS[index],
                            ValidationDomainError.code,
                            "Formula Excel tidak diizinkan pada template import.",
                        )
                    )

            def read_text(
                index: int,
                *,
                required: bool,
                max_length: int | None,
            ) -> str | None:
                cell = row_cells[index]
                field = ITEM_IMPORT_HEADERS[index]
                value = cell.value
                if cell.data_type == "f":
                    return None
                if _item_import_cell_is_blank(value):
                    if required:
                        errors.append(
                            _item_import_error(
                                row_number,
                                field,
                                ValidationDomainError.code,
                                f"Kolom {field} wajib diisi.",
                            )
                        )
                    return None
                if not isinstance(value, str):
                    errors.append(
                        _item_import_error(
                            row_number,
                            field,
                            ValidationDomainError.code,
                            f"Kolom {field} harus berupa teks.",
                        )
                    )
                    return None
                if max_length is not None and len(value) > max_length:
                    errors.append(
                        _item_import_error(
                            row_number,
                            field,
                            ValidationDomainError.code,
                            f"Kolom {field} maksimal {max_length} karakter.",
                        )
                    )
                    return None
                clean_value = value.strip()
                if required and not clean_value:
                    errors.append(
                        _item_import_error(
                            row_number,
                            field,
                            ValidationDomainError.code,
                            f"Kolom {field} wajib diisi.",
                        )
                    )
                    return None
                return clean_value or None

            sku = read_text(0, required=True, max_length=64)
            if sku is not None:
                try:
                    sku = _validate_code_format(
                        sku, field_name="sku", label="SKU barang"
                    )
                except ValidationDomainError as exc:
                    errors.append(
                        _item_import_error(
                            row_number, "sku", exc.code, exc.message
                        )
                    )
                    sku = None
            name = read_text(1, required=True, max_length=200)
            description = read_text(2, required=False, max_length=1000)
            category_name = read_text(3, required=True, max_length=120)
            uom_name = read_text(4, required=True, max_length=60)

            active_cell = row_cells[5]
            if active_cell.data_type == "f":
                is_active = True
            elif _item_import_cell_is_blank(active_cell.value):
                is_active = True
            elif isinstance(active_cell.value, bool):
                is_active = active_cell.value
            elif isinstance(active_cell.value, str) and active_cell.value.strip().lower() in {
                "active",
                "inactive",
            }:
                is_active = active_cell.value.strip().lower() == "active"
            else:
                is_active = True
                errors.append(
                    _item_import_error(
                        row_number,
                        "is_active",
                        ValidationDomainError.code,
                        "Kolom is_active harus berisi TRUE/FALSE atau active/inactive.",
                    )
                )

            records.append(
                {
                    "row": row_number,
                    "sku": sku,
                    "sku_key": sku.lower() if sku is not None else None,
                    "name": name,
                    "description": description,
                    "category_name": category_name,
                    "uom_name": uom_name,
                    "is_active": is_active,
                    "errors": errors,
                }
            )
        return records
    except (BadZipFile, InvalidFileException, OSError, ParseError, ValueError, KeyError) as exc:
        raise ValidationDomainError(
            "Struktur workbook Excel tidak valid.",
            details={"field": "file"},
        ) from exc
    finally:
        workbook.close()


def _parse_supplier_import_workbook(file_bytes: bytes) -> list[dict[str, Any]]:
    if not file_bytes or len(file_bytes) > SUPPLIER_IMPORT_MAX_BYTES:
        raise ValidationDomainError(
            "Ukuran file Excel tidak valid atau melebihi batas 5 MiB.",
            details={"field": "file"},
        )

    try:
        workbook = load_workbook(
            BytesIO(file_bytes), read_only=True, data_only=False
        )
    except (BadZipFile, InvalidFileException, OSError, ParseError, ValueError, KeyError) as exc:
        raise ValidationDomainError(
            "File tidak dapat dibaca sebagai workbook Excel (.xlsx).",
            details={"field": "file"},
        ) from exc

    try:
        if workbook.sheetnames != ["Suppliers"]:
            raise ValidationDomainError(
                "Workbook harus memiliki satu sheet bernama 'Suppliers'.",
                details={"field": "file"},
            )

        worksheet = workbook["Suppliers"]
        if (worksheet.max_column or 0) > len(SUPPLIER_IMPORT_HEADERS):
            raise ValidationDomainError(
                "Workbook tidak boleh memiliki kolom di luar template supplier.",
                details={"field": "file"},
            )
        header_cells = next(
            worksheet.iter_rows(
                min_row=1,
                max_row=1,
                max_col=len(SUPPLIER_IMPORT_HEADERS),
            ),
            (),
        )
        if [cell.value for cell in header_cells] != list(SUPPLIER_IMPORT_HEADERS):
            raise ValidationDomainError(
                "Header workbook tidak sesuai template import supplier.",
                details={"field": "file"},
            )

        records: list[dict[str, Any]] = []
        for row_number, cells in enumerate(
            worksheet.iter_rows(min_row=2, max_col=len(SUPPLIER_IMPORT_HEADERS)),
            start=2,
        ):
            values = [cell.value for cell in cells]
            if all(_item_import_cell_is_blank(value) for value in values):
                continue
            if len(records) >= SUPPLIER_IMPORT_MAX_ROWS:
                raise ValidationDomainError(
                    "Workbook melebihi batas 1.000 baris data.",
                    details={"field": "file"},
                )

            errors: list[dict[str, Any]] = []
            for index, cell in enumerate(cells):
                if cell.data_type == "f":
                    errors.append(
                        _item_import_error(
                            row_number,
                            SUPPLIER_IMPORT_HEADERS[index],
                            ValidationDomainError.code,
                            "Formula Excel tidak diizinkan pada template import.",
                        )
                    )

            def read_text(
                index: int,
                *,
                required: bool,
                max_length: int,
            ) -> str | None:
                cell = cells[index]
                field = SUPPLIER_IMPORT_HEADERS[index]
                if cell.data_type == "f":
                    return None
                value = cell.value
                if _item_import_cell_is_blank(value):
                    if required:
                        errors.append(
                            _item_import_error(
                                row_number,
                                field,
                                ValidationDomainError.code,
                                f"Kolom {field} wajib diisi.",
                            )
                        )
                    return None
                if not isinstance(value, str):
                    errors.append(
                        _item_import_error(
                            row_number,
                            field,
                            ValidationDomainError.code,
                            f"Kolom {field} harus berupa teks.",
                        )
                    )
                    return None
                if len(value) > max_length:
                    errors.append(
                        _item_import_error(
                            row_number,
                            field,
                            ValidationDomainError.code,
                            f"Kolom {field} maksimal {max_length} karakter.",
                        )
                    )
                    return None
                clean_value = value.strip()
                if required and not clean_value:
                    errors.append(
                        _item_import_error(
                            row_number,
                            field,
                            ValidationDomainError.code,
                            f"Kolom {field} wajib diisi.",
                        )
                    )
                    return None
                return clean_value or None

            code = read_text(0, required=True, max_length=50)
            if code is not None:
                try:
                    code = _validate_code_format(
                        code, field_name="code", label="Kode pemasok"
                    )
                except ValidationDomainError as exc:
                    errors.append(
                        _item_import_error(row_number, "code", exc.code, exc.message)
                    )
                    code = None
            name = read_text(1, required=True, max_length=150)
            contact_person = read_text(2, required=False, max_length=120)
            phone = read_text(3, required=False, max_length=30)
            email = read_text(4, required=False, max_length=255)
            address = read_text(5, required=False, max_length=1000)

            if phone is not None:
                try:
                    phone = _validate_optional_phone(phone)
                except ValidationDomainError as exc:
                    errors.append(
                        _item_import_error(row_number, "phone", exc.code, exc.message)
                    )
            if email is not None:
                email = email.lower()
                if not EMAIL_REGEX.match(email):
                    errors.append(
                        _item_import_error(
                            row_number,
                            "email",
                            ValidationDomainError.code,
                            "Format alamat email pemasok tidak valid.",
                        )
                    )

            active_cell = cells[6]
            if active_cell.data_type == "f":
                is_active = True
            elif _item_import_cell_is_blank(active_cell.value):
                is_active = True
            elif isinstance(active_cell.value, bool):
                is_active = active_cell.value
            elif isinstance(active_cell.value, str) and active_cell.value.strip().lower() in {
                "active",
                "inactive",
            }:
                is_active = active_cell.value.strip().lower() == "active"
            else:
                is_active = True
                errors.append(
                    _item_import_error(
                        row_number,
                        "is_active",
                        ValidationDomainError.code,
                        "Kolom is_active harus berisi TRUE/FALSE atau active/inactive.",
                    )
                )

            records.append(
                {
                    "row": row_number,
                    "code": code,
                    "code_key": code.lower() if code is not None else None,
                    "name": name,
                    "contact_person": contact_person,
                    "phone": phone,
                    "email": email,
                    "address": address,
                    "is_active": is_active,
                    "errors": errors,
                }
            )
        return records
    except (BadZipFile, InvalidFileException, OSError, ParseError, ValueError, KeyError) as exc:
        raise ValidationDomainError(
            "Struktur workbook Excel tidak valid.",
            details={"field": "file"},
        ) from exc
    finally:
        workbook.close()


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


def _validate_optional_phone(phone: str | None) -> str | None:
    if phone is None:
        return None
    clean = phone.strip()
    if not clean:
        return None
    digit_count = sum(ch.isdigit() for ch in clean)
    if not PHONE_REGEX.match(clean) or digit_count < 6:
        raise ValidationDomainError(
            "Format nomor telepon pemasok tidak valid (gunakan 6-30 karakter angka, +, -, tanda kurung, atau spasi).",
            details={"field": "phone", "value": clean},
        )
    return clean


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
    clean_code = _validate_code_format(clean_code, field_name="code", label="Kode UoM")

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
            new_code = _validate_code_format(code, field_name="code", label="Kode UoM")
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

        if bool(existing["allow_decimal"]) and not new_allow_decimal:
            if master_repo.is_uom_referenced_by_any_item(conn, uom_id):
                raise EntityInUse(
                    "Atribut allow_decimal pada UoM tidak dapat diubah menjadi FALSE karena UoM sudah digunakan oleh barang.",
                    details={"uom_id": uom_id, "field": "allow_decimal"},
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
    clean_code = _validate_code_format(
        clean_code, field_name="code", label="Kode pemasok"
    )
    clean_phone = _validate_optional_phone(phone)

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
            contact_person=contact_person.strip()
            if contact_person and contact_person.strip()
            else None,
            phone=clean_phone,
            email=clean_email,
            address=address.strip() if address and address.strip() else None,
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


def import_suppliers_from_excel(
    conn: Connection[dict[str, Any]],
    *,
    file_name: str | None,
    file_bytes: bytes,
    actor: dict[str, Any],
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Memvalidasi dan membuat supplier dari workbook dengan hasil parsial per baris."""
    if not file_name or not file_name.lower().endswith(".xlsx"):
        raise ValidationDomainError(
            "File harus menggunakan format .xlsx.",
            details={"field": "file"},
        )
    records = _parse_supplier_import_workbook(file_bytes)
    if not records:
        return {
            "total_rows": 0,
            "imported_count": 0,
            "failed_count": 0,
            "errors": [],
        }

    code_counts = Counter(
        record["code_key"] for record in records if record["code_key"] is not None
    )
    for record in records:
        code_key = record["code_key"]
        if code_key is not None and code_counts[code_key] > 1:
            record["errors"].append(
                _item_import_error(
                    record["row"],
                    "code",
                    DuplicateError.code,
                    "Kode pemasok muncul lebih dari satu kali di dalam file.",
                )
            )

    code_keys = sorted(
        {
            record["code_key"]
            for record in records
            if record["code_key"] is not None
        }
    )

    with conn.transaction():
        existing_code_keys = master_repo.list_existing_supplier_code_keys(
            conn, code_keys
        )
        for record in records:
            code_key = record["code_key"]
            if code_key is not None and code_key in existing_code_keys:
                record["errors"].append(
                    _item_import_error(
                        record["row"],
                        "code",
                        DuplicateError.code,
                        "Kode pemasok sudah terdaftar.",
                    )
                )

        valid_records = [record for record in records if not record["errors"]]
        inserted_suppliers = master_repo.insert_suppliers_batch(
            conn,
            suppliers=valid_records,
            created_by=int(actor["id"]),
        )
        inserted_keys = {str(supplier["code_key"]) for supplier in inserted_suppliers}
        for record in valid_records:
            if record["code_key"] not in inserted_keys:
                record["errors"].append(
                    _item_import_error(
                        record["row"],
                        "code",
                        DuplicateError.code,
                        "Kode pemasok sudah terdaftar.",
                    )
                )

        audit_service.record_many(
            conn,
            [
                {
                    "user_id": int(actor["id"]),
                    "action": "SUPPLIER_CREATED",
                    "entity_type": "suppliers",
                    "entity_id": supplier["id"],
                    "old_values": None,
                    "new_values": {
                        "id": supplier["id"],
                        "code": supplier["code"],
                        "name": supplier["name"],
                        "contact_person": supplier["contact_person"],
                        "phone": supplier["phone"],
                        "email": supplier["email"],
                        "address": supplier["address"],
                        "is_active": supplier["is_active"],
                    },
                    "ip_address": ip_address,
                }
                for supplier in inserted_suppliers
            ],
        )

    row_errors = [error for record in records for error in record["errors"]]
    failed_rows = {error["row"] for error in row_errors}
    row_errors.sort(key=lambda error: (error["row"], error["field"], error["code"]))
    return {
        "total_rows": len(records),
        "imported_count": len(inserted_suppliers),
        "failed_count": len(failed_rows),
        "errors": row_errors,
    }


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
            new_code = _validate_code_format(
                code, field_name="code", label="Kode pemasok"
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
            (contact_person.strip() or None)
            if contact_person is not None
            else existing["contact_person"]
        )
        new_phone = (
            _validate_optional_phone(phone)
            if phone is not None
            else existing["phone"]
        )
        new_address = (
            (address.strip() or None)
            if address is not None
            else existing["address"]
        )

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
    clean_sku = _validate_code_format(clean_sku, field_name="sku", label="SKU barang")

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


def import_items_from_excel(
    conn: Connection[dict[str, Any]],
    *,
    file_name: str | None,
    file_bytes: bytes,
    actor: dict[str, Any],
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Validasi dan buat item dari workbook Excel dengan hasil parsial per baris."""
    if not file_name or not file_name.lower().endswith(".xlsx"):
        raise ValidationDomainError(
            "File harus menggunakan format .xlsx.",
            details={"field": "file"},
        )
    records = _parse_item_import_workbook(file_bytes)
    if not records:
        return {
            "total_rows": 0,
            "imported_count": 0,
            "failed_count": 0,
            "errors": [],
        }

    sku_counts = Counter(
        record["sku_key"] for record in records if record["sku_key"] is not None
    )
    for record in records:
        sku_key = record["sku_key"]
        if sku_key is not None and sku_counts[sku_key] > 1:
            record["errors"].append(
                _item_import_error(
                    record["row"],
                    "sku",
                    DuplicateError.code,
                    "SKU muncul lebih dari satu kali di dalam file.",
                )
            )

    category_names = sorted(
        {
            record["category_name"].lower()
            for record in records
            if record["category_name"] is not None
        }
    )
    uom_names = sorted(
        {
            record["uom_name"].lower()
            for record in records
            if record["uom_name"] is not None
        }
    )
    sku_keys = sorted(
        {
            record["sku_key"]
            for record in records
            if record["sku_key"] is not None
        }
    )

    with conn.transaction():
        categories = master_repo.list_item_import_categories(conn, category_names)
        uoms = master_repo.list_item_import_uoms(conn, uom_names)
        existing_sku_keys = master_repo.list_existing_item_sku_keys(conn, sku_keys)
        category_by_name: dict[str, list[dict[str, Any]]] = {}
        for row in categories:
            category_by_name.setdefault(str(row["name"]).lower(), []).append(row)
        uom_by_name: dict[str, list[dict[str, Any]]] = {}
        for row in uoms:
            uom_by_name.setdefault(str(row["name"]).lower(), []).append(row)

        for record in records:
            category_name = record["category_name"]
            if category_name is not None:
                matching_categories = category_by_name.get(category_name.lower(), [])
                if not matching_categories:
                    record["errors"].append(
                        _item_import_error(
                            record["row"],
                            "category_name",
                            NotFoundError.code,
                            "Kategori tidak ditemukan.",
                        )
                    )
                elif len(matching_categories) > 1:
                    record["errors"].append(
                        _item_import_error(
                            record["row"],
                            "category_name",
                            ValidationDomainError.code,
                            "Nama kategori ambigu; minta administrator meninjau data master.",
                        )
                    )
                elif not matching_categories[0]["is_active"]:
                    record["errors"].append(
                        _item_import_error(
                            record["row"],
                            "category_name",
                            InactiveReferenceError.code,
                            "Kategori yang dipilih berstatus tidak aktif.",
                        )
                    )
                else:
                    record["category_id"] = int(matching_categories[0]["id"])

            uom_name = record["uom_name"]
            if uom_name is not None:
                matching_uoms = uom_by_name.get(uom_name.lower(), [])
                if not matching_uoms:
                    record["errors"].append(
                        _item_import_error(
                            record["row"],
                            "uom_name",
                            NotFoundError.code,
                            "Satuan ukur (UoM) tidak ditemukan.",
                        )
                    )
                elif len(matching_uoms) > 1:
                    candidate_codes = ", ".join(
                        sorted(str(uom["code"]) for uom in matching_uoms)
                    )
                    record["errors"].append(
                        _item_import_error(
                            record["row"],
                            "uom_name",
                            ValidationDomainError.code,
                            f"Nama satuan ambigu; kode yang cocok: {candidate_codes}.",
                        )
                    )
                elif not matching_uoms[0]["is_active"]:
                    record["errors"].append(
                        _item_import_error(
                            record["row"],
                            "uom_name",
                            InactiveReferenceError.code,
                            "Satuan ukur (UoM) yang dipilih berstatus tidak aktif.",
                        )
                    )
                else:
                    record["uom_id"] = int(matching_uoms[0]["id"])

            sku_key = record["sku_key"]
            if sku_key is not None and sku_key in existing_sku_keys:
                record["errors"].append(
                    _item_import_error(
                        record["row"],
                        "sku",
                        DuplicateError.code,
                        "SKU sudah terdaftar.",
                    )
                )

        valid_records = [record for record in records if not record["errors"]]
        inserted_items = master_repo.insert_items_batch(
            conn,
            items=valid_records,
            created_by=int(actor["id"]),
        )
        inserted_keys = {str(item["sku_key"]) for item in inserted_items}
        for record in valid_records:
            if record["sku_key"] not in inserted_keys:
                record["errors"].append(
                    _item_import_error(
                        record["row"],
                        "sku",
                        DuplicateError.code,
                        "SKU sudah terdaftar.",
                    )
                )

        audit_service.record_many(
            conn,
            [
                {
                    "user_id": int(actor["id"]),
                    "action": "ITEM_CREATED",
                    "entity_type": "items",
                    "entity_id": item["id"],
                    "old_values": None,
                    "new_values": {
                        "id": item["id"],
                        "sku": item["sku"],
                        "name": item["name"],
                        "description": item["description"],
                        "category_id": item["category_id"],
                        "uom_id": item["uom_id"],
                        "is_active": item["is_active"],
                    },
                    "ip_address": ip_address,
                }
                for item in inserted_items
            ],
        )

    row_errors = [error for record in records for error in record["errors"]]
    failed_rows = {error["row"] for error in row_errors}
    row_errors.sort(key=lambda error: (error["row"], error["field"], error["code"]))
    return {
        "total_rows": len(records),
        "imported_count": len(inserted_items),
        "failed_count": len(failed_rows),
        "errors": row_errors,
    }


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
            new_sku = _validate_code_format(sku, field_name="sku", label="SKU barang")
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

