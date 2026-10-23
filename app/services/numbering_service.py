"""Service generator nomor dokumen unik {PREFIX}-{YYYYMM}-{NNNN} (FR-10)."""

from datetime import date, datetime, timezone
from typing import Any

from psycopg import Connection

from app.core.exceptions import ValidationDomainError
from app.repositories import sequence_repo
from app.utils.enums import DocType

ALLOWED_DOC_TYPES: frozenset[str] = frozenset(t.value for t in DocType)


def generate_document_number(
    conn: Connection[dict[str, Any]],
    doc_type: str | DocType,
    *,
    reference_date: date | datetime | None = None,
) -> str:
    """Menghasilkan nomor dokumen unik berformat {PREFIX}-{YYYYMM}-{NNNN} (contoh: PO-202610-0001).

    Harus dipanggil di dalam transaksi pembuatan dokumen.
    Nomor dokumen yang dibatalkan tidak dipakai ulang (FR-10).
    """
    prefix = doc_type.value if isinstance(doc_type, DocType) else str(doc_type).strip().upper()
    if prefix not in ALLOWED_DOC_TYPES:
        raise ValidationDomainError(
            f"Tipe dokumen '{prefix}' tidak valid.",
            details={"doc_type": prefix, "allowed": sorted(ALLOWED_DOC_TYPES)},
        )

    target_date = reference_date or datetime.now(timezone.utc)
    period = target_date.strftime("%Y%m")
    seq_num = sequence_repo.increment_and_get_sequence(
        conn, doc_type=prefix, period=period
    )
    return f"{prefix}-{period}-{seq_num:04d}"

