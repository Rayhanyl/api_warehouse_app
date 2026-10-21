"""Utilitas pagination dan pembuatan klausa ORDER BY aman berbasis whitelist (FR-11, PRD 7.2)."""

from app.core.exceptions import ValidationDomainError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def normalize_pagination(limit: int = DEFAULT_LIMIT, offset: int = 0) -> tuple[int, int]:
    """Memvalidasi dan menormalisasi parameter limit (1..200, bawaan 50) dan offset (>= 0)."""
    if limit < 1 or limit > MAX_LIMIT:
        raise ValidationDomainError(
            f"Parameter limit harus berada di antara 1 dan {MAX_LIMIT}.",
            details={"limit": limit, "max_limit": MAX_LIMIT},
        )
    if offset < 0:
        raise ValidationDomainError(
            "Parameter offset tidak boleh negatif.",
            details={"offset": offset},
        )
    return limit, offset


def build_order_by(
    sort_by: str | None,
    sort_dir: str | None,
    allowed_columns: dict[str, str],
    default_column: str,
    default_dir: str = "DESC",
) -> str:
    """Menyusun ekspresi ORDER BY hanya dari whitelist kolom yang diizinkan."""
    if sort_by is None:
        col_sql = allowed_columns[default_column]
    else:
        if sort_by not in allowed_columns:
            raise ValidationDomainError(
                f"Kolom pengurutan '{sort_by}' tidak diizinkan.",
                details={
                    "sort_by": sort_by,
                    "allowed_columns": sorted(allowed_columns.keys()),
                },
            )
        col_sql = allowed_columns[sort_by]

    direction = (sort_dir or default_dir).upper()
    if direction not in ("ASC", "DESC"):
        raise ValidationDomainError(
            "Arah pengurutan (sort_dir) harus 'asc' atau 'desc'.",
            details={"sort_dir": sort_dir},
        )

    return f"{col_sql} {direction}"

