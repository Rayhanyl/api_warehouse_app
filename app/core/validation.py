"""Helper validasi terpusat dan lokalisasi error Pydantic untuk backend WMS."""

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from app.core.exceptions import ValidationDomainError

# Konstanta regex & numerik terpusat (PRD 6.3, 6.9)
CODE_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
PHONE_REGEX = re.compile(r"^[0-9+() -]{6,30}$")
ICON_REGEX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MENU_PATH_REGEX = re.compile(r"^/[^\s]*$")

FOUR_PLACES = Decimal("0.0001")
ZERO = Decimal("0.0000")
MAX_QTY = Decimal("99999999999999.9999")

_SENSITIVE_FIELD_PARTS = (
    "password",
    "passcode",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "authorization",
)

FIELD_LABELS_ID: dict[str, str] = {
    "username": "Username",
    "email": "Email",
    "password": "Kata sandi",
    "current_password": "Kata sandi saat ini",
    "new_password": "Kata sandi baru",
    "full_name": "Nama lengkap",
    "role_id": "Peran",
    "warehouse_id": "Gudang",
    "warehouse_ids": "Daftar gudang",
    "from_warehouse_id": "Gudang asal",
    "to_warehouse_id": "Gudang tujuan",
    "from_location_id": "Lokasi asal",
    "to_location_id": "Lokasi tujuan",
    "location_id": "Lokasi penyimpanan",
    "supplier_id": "Pemasok",
    "category_id": "Kategori",
    "uom_id": "Satuan (UoM)",
    "item_id": "Barang",
    "po_id": "Purchase Order",
    "po_line_id": "Baris PO",
    "line_id": "Baris transaksi",
    "parent_id": "Menu induk",
    "permission_id": "Hak akses",
    "permission_ids": "Daftar hak akses",
    "code": "Kode",
    "sku": "SKU",
    "barcode": "Barcode",
    "name": "Nama",
    "description": "Deskripsi",
    "contact_person": "Kontak person",
    "phone": "Nomor telepon",
    "address": "Alamat",
    "path": "Path rute",
    "icon": "Ikon",
    "sort_order": "Urutan",
    "order_date": "Tanggal PO",
    "expected_date": "Estimasi tanggal tiba",
    "received_date": "Tanggal penerimaan",
    "opname_date": "Tanggal opname",
    "qty": "Jumlah",
    "qty_ordered": "Jumlah pesan",
    "qty_received": "Jumlah diterima",
    "qty_physical": "Jumlah fisik",
    "unit_price": "Harga satuan",
    "allow_decimal": "Izinkan desimal",
    "is_active": "Status aktif",
    "notes": "Catatan",
    "reason": "Alasan",
    "lines": "Daftar barang",
    "refresh_token": "Refresh token",
}


def _is_sensitive_loc(loc: list[Any] | tuple[Any, ...]) -> bool:
    for part in loc:
        lower = str(part).lower()
        if any(key in lower for key in _SENSITIVE_FIELD_PARTS):
            return True
    return False


def clean_optional_str(value: str | None) -> str | None:
    """Membersihkan spasi di awal/akhir string opsional dan mengubah string kosong menjadi None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def ensure_non_blank_str(
    value: str,
    *,
    field_name: str,
    label: str,
    max_length: int | None = None,
) -> str:
    """Memastikan string wajib tidak kosong/spasi saja serta memenuhi batas panjang."""
    clean = value.strip()
    if not clean:
        raise ValidationDomainError(
            f"{label} tidak boleh kosong.",
            details={"field": field_name},
        )
    if max_length is not None and len(clean) > max_length:
        raise ValidationDomainError(
            f"{label} maksimal {max_length} karakter.",
            details={"field": field_name, "max_length": max_length},
        )
    return clean


def validate_code_format(
    value: str,
    *,
    field_name: str,
    label: str,
    max_length: int | None = None,
) -> str:
    """Memvalidasi kode/SKU/barcode agar diawali alfanumerik tanpa spasi."""
    clean = ensure_non_blank_str(
        value, field_name=field_name, label=label, max_length=max_length
    )
    if not CODE_REGEX.match(clean):
        raise ValidationDomainError(
            f"Format {label.lower()} tidak valid; hanya boleh diawali huruf/angka dan berisi huruf, angka, titik (.), garis bawah (_), garis miring (/), atau tanda hubung (-) tanpa spasi.",
            details={"field": field_name, "value": clean},
        )
    return clean


def validate_email_format(email: str, *, field_name: str = "email") -> str:
    """Memvalidasi format email standar dan menormalisasi ke huruf kecil."""
    clean = email.strip().lower()
    if not clean:
        raise ValidationDomainError(
            "Email tidak boleh kosong.",
            details={"field": field_name},
        )
    if not EMAIL_REGEX.match(clean):
        raise ValidationDomainError(
            "Format alamat email tidak valid.",
            details={"field": field_name, "value": clean},
        )
    return clean


def validate_username_format(username: str, *, field_name: str = "username") -> str:
    """Memvalidasi format username (3-64 karakter, diawali alfanumerik)."""
    clean = username.strip()
    if not USERNAME_REGEX.match(clean):
        raise ValidationDomainError(
            "Username hanya boleh berisi huruf, angka, titik, underscore, atau strip (3-64 karakter) dan diawali huruf/angka.",
            details={"field": field_name, "value": clean},
        )
    return clean


def validate_optional_phone(
    phone: str | None, *, field_name: str = "phone", label: str = "Nomor telepon"
) -> str | None:
    """Memvalidasi nomor telepon opsional (6-30 karakter, minimal 6 digit angka)."""
    clean = clean_optional_str(phone)
    if clean is None:
        return None
    digit_count = sum(ch.isdigit() for ch in clean)
    if not PHONE_REGEX.match(clean) or digit_count < 6:
        raise ValidationDomainError(
            f"Format {label.lower()} tidak valid (gunakan 6-30 karakter angka, +, -, tanda kurung, atau spasi dengan minimal 6 digit angka).",
            details={"field": field_name, "value": clean},
        )
    return clean


def validate_menu_path(path: str, *, field_name: str = "path") -> str:
    """Memvalidasi path rute menu agar diawali '/' dan tidak mengandung spasi."""
    clean = path.strip()
    if not clean or not MENU_PATH_REGEX.match(clean):
        raise ValidationDomainError(
            "Path menu harus diawali '/' dan tidak boleh mengandung spasi.",
            details={"field": field_name, "value": clean},
        )
    return clean


def validate_icon_format(icon: str | None, *, field_name: str = "icon") -> str | None:
    """Memvalidasi nama ikon kebab-case (mis. 'package-check')."""
    clean = clean_optional_str(icon)
    if clean is None:
        return None
    if not ICON_REGEX.match(clean):
        raise ValidationDomainError(
            "Format nama icon tidak valid; gunakan huruf kecil, angka, dan tanda hubung (kebab-case, mis. 'package-check').",
            details={"field": field_name, "value": clean},
        )
    return clean


def normalize_decimal_qty(
    value: Any,
    *,
    field_name: str = "qty",
    allow_zero: bool = False,
) -> Decimal:
    """Memastikan kuantitas bertipe Decimal (bukan float), maksimal 4 desimal, dalam batas NUMERIC(18,4)."""
    if isinstance(value, float):
        raise ValidationDomainError(
            f"Field '{field_name}' harus bertipe Decimal, tidak boleh float.",
            details={"field": field_name, "value": str(value)},
        )
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
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
    if quantized > MAX_QTY:
        raise ValidationDomainError(
            f"Field '{field_name}' melebihi batas maksimum NUMERIC(18,4) ({MAX_QTY}).",
            details={"field": field_name, "value": str(quantized), "max_qty": str(MAX_QTY)},
        )
    return quantized


# ============================================================================
# Helper Validator untuk Skema Pydantic (mengangkat ValueError -> 422 terstruktur)
# ============================================================================
def pydantic_required_str(value: Any, *, label: str = "Field") -> Any:
    if not isinstance(value, str):
        return value
    clean = value.strip()
    if not clean:
        raise ValueError(f"{label} tidak boleh kosong atau hanya berisi spasi.")
    return clean


def pydantic_optional_str(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    clean = value.strip()
    return clean or None


def pydantic_optional_non_blank_str(value: Any, *, label: str = "Field") -> Any:
    if value is None or not isinstance(value, str):
        return value
    clean = value.strip()
    if not clean:
        raise ValueError(f"{label} tidak boleh kosong atau hanya berisi spasi.")
    return clean


def pydantic_validate_code(value: Any, *, label: str = "Kode") -> Any:
    if not isinstance(value, str):
        return value
    clean = pydantic_required_str(value, label=label)
    if not CODE_REGEX.match(clean):
        raise ValueError(
            f"Format {label.lower()} tidak valid; gunakan huruf/angka di awal dan hanya huruf, angka, '.', '_', '/', atau '-' tanpa spasi."
        )
    return clean


def pydantic_validate_optional_code(value: Any, *, label: str = "Kode") -> Any:
    if value is None or not isinstance(value, str):
        return value
    clean = value.strip()
    if not clean:
        return None
    return pydantic_validate_code(clean, label=label)


def pydantic_validate_email(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    clean = value.strip().lower()
    if not clean:
        raise ValueError("Email tidak boleh kosong.")
    if not EMAIL_REGEX.match(clean):
        raise ValueError("Format alamat email tidak valid.")
    return clean


def pydantic_validate_username(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    clean = value.strip()
    if not USERNAME_REGEX.match(clean):
        raise ValueError(
            "Username harus 3-64 karakter, diawali huruf/angka, dan hanya boleh berisi huruf, angka, '.', '_', atau '-'."
        )
    return clean


def pydantic_validate_optional_phone(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    clean = value.strip()
    if not clean:
        return None
    digit_count = sum(ch.isdigit() for ch in clean)
    if not PHONE_REGEX.match(clean) or digit_count < 6:
        raise ValueError(
            "Format nomor telepon tidak valid (gunakan 6-30 karakter dengan minimal 6 digit angka)."
        )
    return clean


def pydantic_validate_menu_path(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    clean = value.strip()
    if not clean or not MENU_PATH_REGEX.match(clean):
        raise ValueError("Path menu harus diawali '/' dan tidak boleh mengandung spasi.")
    return clean


def pydantic_validate_icon(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    clean = value.strip()
    if not clean:
        return None
    if not ICON_REGEX.match(clean):
        raise ValueError(
            "Format nama ikon tidak valid; gunakan huruf kecil, angka, dan tanda hubung (kebab-case)."
        )
    return clean


def pydantic_validate_decimal_qty(
    value: Any,
    *,
    label: str = "Jumlah",
    allow_zero: bool = False,
) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} harus berupa angka yang valid.")
    if isinstance(value, float):
        raise ValueError(f"{label} tidak boleh dikirim sebagai float; gunakan string atau desimal.")
    try:
        dec = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Format angka pada {label.lower()} tidak valid.") from exc
    if not dec.is_finite():
        raise ValueError(f"{label} harus berupa angka yang valid.")
    if dec.quantize(FOUR_PLACES) != dec:
        raise ValueError(f"{label} maksimal memiliki 4 angka di belakang koma.")
    if dec < ZERO or (not allow_zero and dec == ZERO):
        rule = "lebih besar dari atau sama dengan 0" if allow_zero else "lebih besar dari 0"
        raise ValueError(f"{label} harus {rule}.")
    if dec > MAX_QTY:
        raise ValueError(f"{label} melebihi batas maksimum {MAX_QTY}.")
    return dec.quantize(FOUR_PLACES)


def pydantic_validate_positive_id_list(
    values: list[int] | None, *, label: str = "Daftar ID"
) -> list[int] | None:
    if values is None:
        return None
    for item in values:
        if item <= 0:
            raise ValueError(f"Setiap item pada {label.lower()} harus berupa ID positif (> 0).")
    return values


# ============================================================================
# Lokalisasi Pydantic RequestValidationError -> Response 422 Terstruktur
# ============================================================================
def _humanize_field_name(loc: list[Any] | tuple[Any, ...]) -> tuple[str, str]:
    """Mengubah tuple loc Pydantic menjadi (field_path, label_ramah_indonesia)."""
    parts = [str(part) for part in loc]
    if parts and parts[0] in {"body", "query", "path", "header", "cookie"}:
        parts = parts[1:]
    if not parts:
        return "payload", "Payload permintaan"
    field_path = ".".join(parts)
    last_non_index = next(
        (part for part in reversed(parts) if not part.isdigit()),
        parts[-1],
    )
    label = FIELD_LABELS_ID.get(last_non_index, last_non_index.replace("_", " ").capitalize())
    return field_path, label


def _translate_pydantic_message(err: dict[str, Any], label: str) -> str:
    err_type = str(err.get("type", ""))
    ctx = err.get("ctx") or {}
    raw_msg = str(err.get("msg", "")).strip()

    if err_type == "missing":
        return f"{label} wajib diisi."
    if err_type == "string_too_short":
        return f"{label} minimal {ctx.get('min_length', 1)} karakter."
    if err_type == "string_too_long":
        return f"{label} maksimal {ctx.get('max_length', '')} karakter."
    if err_type == "greater_than":
        return f"{label} harus lebih besar dari {ctx.get('gt', 0)}."
    if err_type == "greater_than_equal":
        return f"{label} harus lebih besar dari atau sama dengan {ctx.get('ge', 0)}."
    if err_type == "less_than":
        return f"{label} harus kurang dari {ctx.get('lt', '')}."
    if err_type == "less_than_equal":
        return f"{label} maksimal {ctx.get('le', '')}."
    if err_type == "too_short":
        return f"{label} minimal memiliki {ctx.get('min_length', 1)} item."
    if err_type == "too_long":
        return f"{label} maksimal memiliki {ctx.get('max_length', '')} item."
    if err_type in {"int_parsing", "int_type"}:
        return f"{label} harus berupa bilangan bulat yang valid."
    if err_type in {"decimal_parsing", "decimal_type"}:
        return f"{label} harus berupa angka desimal yang valid."
    if err_type in {"bool_parsing", "bool_type"}:
        return f"{label} harus berupa nilai boolean (true/false)."
    if err_type == "date_from_datetime_parsing":
        return f"Format tanggal pada {label.lower()} tidak valid (gunakan YYYY-MM-DD)."
    if err_type == "list_type":
        return f"{label} harus berupa daftar (array) yang valid."
    if err_type == "extra_forbidden":
        return f"Field '{label}' tidak dikenali atau tidak diizinkan."
    if err_type == "json_invalid":
        return "Format JSON pada body permintaan tidak valid."
    if err_type == "value_error":
        if raw_msg.startswith("Value error, "):
            return raw_msg[len("Value error, "):]
        return raw_msg or f"Nilai pada {label.lower()} tidak valid."
    return raw_msg or f"Nilai pada {label.lower()} tidak valid."


def format_pydantic_errors(
    encoded_errors: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], dict[str, str]]:
    """Menghasilkan pesan ringkas, daftar error berbahasa Indonesia (tanpa nilai sensitif), dan peta field_errors."""
    translated_errors: list[dict[str, Any]] = []
    field_errors: dict[str, str] = {}

    for err in encoded_errors:
        loc = err.get("loc", [])
        field_path, label = _humanize_field_name(loc)
        msg_id = _translate_pydantic_message(err, label)

        item: dict[str, Any] = {
            "loc": [str(part) for part in loc],
            "field": field_path,
            "msg": msg_id,
            "type": str(err.get("type", "")),
        }
        if "input" in err and not _is_sensitive_loc(loc):
            item["input"] = err["input"]

        translated_errors.append(item)
        if field_path not in field_errors:
            field_errors[field_path] = msg_id

    if len(translated_errors) == 1:
        summary_message = translated_errors[0]["msg"]
    elif translated_errors:
        summary_message = (
            f"Terdapat {len(translated_errors)} kesalahan validasi pada data yang dikirim: "
            f"{translated_errors[0]['msg']}"
        )
    else:
        summary_message = "Payload permintaan tidak valid."

    return summary_message, translated_errors, field_errors
