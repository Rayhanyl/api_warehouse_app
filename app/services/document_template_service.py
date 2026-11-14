"""Service pengaturan template dokumen cetak modular & upload logo aman (Tahap 17 / Poin 10)."""

from pathlib import Path
import re
from typing import Any
import uuid

from fastapi import UploadFile
from psycopg import Connection

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationDomainError
from app.repositories import document_template_repo
from app.schemas.document_template import (
    ALLOWED_COLUMNS_BY_TYPE,
    DocumentTemplateUpdate,
)
from app.services import audit_service

MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB
_LOGO_URL_PREFIX = "/api/v1/document-templates/logos/"
_SAFE_FILENAME_REGEX = re.compile(r"^logo-[a-f0-9]{32}\.(png|jpg|webp)$")
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def get_logo_storage_dir() -> Path:
    """Mengembalikan direktori penyimpanan logo yang absolut dan siap tulis."""
    base = Path(settings.upload_dir)
    if not base.is_absolute():
        base = _BACKEND_ROOT / base
    logo_dir = (base / "document_logos").resolve()
    logo_dir.mkdir(parents=True, exist_ok=True)
    return logo_dir


def _validate_document_type(document_type: str) -> str:
    normalized = (document_type or "").strip().upper()
    if normalized not in ALLOWED_COLUMNS_BY_TYPE:
        allowed = ", ".join(ALLOWED_COLUMNS_BY_TYPE.keys())
        raise ValidationDomainError(
            f"Jenis dokumen '{document_type}' tidak valid. Pilihan yang didukung: {allowed}.",
            details={"field": "document_type", "value": document_type},
        )
    return normalized


def _detect_image_format(data: bytes) -> tuple[str, str]:
    """Mendeteksi tipe gambar berdasarkan magic bytes (hanya PNG, JPEG, WEBP)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp", "image/webp"
    raise ValidationDomainError(
        "Format logo tidak didukung atau berkas rusak. Gunakan gambar PNG, JPG/JPEG, atau WEBP.",
        details={"field": "file"},
    )


def _delete_unused_local_logo(
    conn: Connection[dict[str, Any]],
    logo_url: str | None,
) -> None:
    if not logo_url or not logo_url.startswith(_LOGO_URL_PREFIX):
        return
    filename = logo_url[len(_LOGO_URL_PREFIX) :]
    if not _SAFE_FILENAME_REGEX.match(filename):
        return
    if document_template_repo.is_logo_referenced_elsewhere(conn, logo_url):
        return
    target = (get_logo_storage_dir() / filename).resolve()
    if target.is_file():
        target.unlink(missing_ok=True)


def list_templates(conn: Connection[dict[str, Any]]) -> list[dict[str, Any]]:
    return document_template_repo.list_templates(conn)


def get_template(
    conn: Connection[dict[str, Any]],
    document_type: str,
) -> dict[str, Any]:
    doc_type = _validate_document_type(document_type)
    row = document_template_repo.get_template_by_type(conn, doc_type)
    if not row:
        raise NotFoundError(
            f"Template untuk jenis dokumen '{doc_type}' tidak ditemukan.",
            details={"document_type": doc_type},
        )
    return row


def update_template(
    conn: Connection[dict[str, Any]],
    *,
    document_type: str,
    payload: DocumentTemplateUpdate,
    actor: dict[str, Any],
    ip_address: str | None = None,
) -> dict[str, Any]:
    doc_type = _validate_document_type(document_type)
    allowed_keys = set(ALLOWED_COLUMNS_BY_TYPE[doc_type])
    invalid_keys = [col.key for col in payload.table_columns if col.key not in allowed_keys]
    if invalid_keys:
        raise ValidationDomainError(
            f"Kolom tabel {', '.join(invalid_keys)} tidak valid untuk dokumen {doc_type}.",
            details={
                "field": "table_columns",
                "invalid_keys": invalid_keys,
                "allowed_keys": sorted(allowed_keys),
            },
        )

    data = payload.model_dump()
    with conn.transaction():
        old_row = document_template_repo.get_template_by_type(conn, doc_type)
        updated = document_template_repo.upsert_template(
            conn,
            document_type=doc_type,
            data=data,
            updated_by=int(actor["id"]),
        )
        old_logo_url = old_row.get("logo_url") if old_row else None
        if old_logo_url and old_logo_url != updated.get("logo_url"):
            _delete_unused_local_logo(conn, old_logo_url)

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="UPDATE",
            entity_type="document_templates",
            entity_id=doc_type,
            old_values=old_row,
            new_values=updated,
            ip_address=ip_address,
            details={"document_type": doc_type},
        )
    return updated


async def save_uploaded_logo(
    conn: Connection[dict[str, Any]],
    *,
    file: UploadFile,
    actor: dict[str, Any],
    ip_address: str | None = None,
) -> dict[str, Any]:
    raw = await file.read(MAX_LOGO_BYTES + 1)
    if not raw:
        raise ValidationDomainError(
            "Berkas logo tidak boleh kosong.",
            details={"field": "file"},
        )
    if len(raw) > MAX_LOGO_BYTES:
        raise ValidationDomainError(
            "Ukuran berkas logo melebihi batas maksimum 2 MB.",
            details={"field": "file", "max_bytes": MAX_LOGO_BYTES},
        )

    ext, detected_content_type = _detect_image_format(raw)
    filename = f"logo-{uuid.uuid4().hex}{ext}"
    target_path = (get_logo_storage_dir() / filename).resolve()
    target_path.write_bytes(raw)
    logo_url = f"{_LOGO_URL_PREFIX}{filename}"

    with conn.transaction():
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="UPLOAD_LOGO",
            entity_type="document_templates",
            entity_id=filename,
            old_values=None,
            new_values={
                "logo_url": logo_url,
                "content_type": detected_content_type,
                "size_bytes": len(raw),
            },
            ip_address=ip_address,
        )

    return {
        "logo_url": logo_url,
        "filename": filename,
        "content_type": detected_content_type,
        "size_bytes": len(raw),
    }


def resolve_logo_file_path(filename: str) -> tuple[Path, str]:
    """Memvalidasi nama file logo agar bebas path traversal sebelum dikirim."""
    clean_name = (filename or "").strip()
    if not _SAFE_FILENAME_REGEX.match(clean_name):
        raise NotFoundError("Berkas logo tidak ditemukan.")

    storage_dir = get_logo_storage_dir()
    candidate = (storage_dir / clean_name).resolve()
    if not candidate.is_relative_to(storage_dir) or not candidate.is_file():
        raise NotFoundError("Berkas logo tidak ditemukan.")

    suffix = candidate.suffix.lower()
    media_type = (
        "image/png"
        if suffix == ".png"
        else "image/jpeg"
        if suffix == ".jpg"
        else "image/webp"
    )
    return candidate, media_type
