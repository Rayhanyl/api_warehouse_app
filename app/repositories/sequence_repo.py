"""Repository SQL untuk penomoran dokumen berurutan (document_sequences, FR-10)."""

from typing import Any

from psycopg import Connection


def increment_and_get_sequence(
    conn: Connection[dict[str, Any]],
    *,
    doc_type: str,
    period: str,
) -> int:
    """Menaikkan dan mengambil nomor urut dokumen secara atomik (aman terhadap konkurensi)."""
    row = conn.execute(
        """
        INSERT INTO document_sequences (doc_type, period, last_value, updated_at)
        VALUES (%s, %s, 1, CURRENT_TIMESTAMP)
        ON CONFLICT (doc_type, period)
        DO UPDATE SET
            last_value = document_sequences.last_value + 1,
            updated_at = CURRENT_TIMESTAMP
        RETURNING last_value
        """,
        (doc_type, period),
    ).fetchone()
    assert row is not None
    return int(row["last_value"])

