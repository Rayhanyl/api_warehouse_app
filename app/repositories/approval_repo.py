"""Repository untuk riwayat persetujuan & penolakan berjenjang (approval_logs, Tahap 34)."""

from typing import Any

from psycopg import Connection


def insert_approval_log(
    conn: Connection[dict[str, Any]],
    *,
    doc_type: str,
    doc_id: int,
    approval_level: int,
    action: str,
    actor_id: int | None,
    actor_name: str,
    actor_role: str,
    notes: str | None = None,
) -> dict[str, Any]:
    """Menyimpan satu entri riwayat submit / approve / reject untuk PO atau Stock Opname."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO approval_logs (
                doc_type,
                doc_id,
                approval_level,
                action,
                actor_id,
                actor_name,
                actor_role,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, doc_type, doc_id, approval_level, action, actor_id, actor_name, actor_role, notes, created_at
            """,
            (doc_type, doc_id, approval_level, action, actor_id, actor_name, actor_role, notes),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError("Gagal menyimpan entri approval_logs.")
    return row


def list_approval_logs(
    conn: Connection[dict[str, Any]],
    *,
    doc_type: str,
    doc_id: int,
) -> list[dict[str, Any]]:
    """Mengambil kronologi approval_logs milik dokumen tertentu secara berurutan."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, doc_type, doc_id, approval_level, action, actor_id, actor_name, actor_role, notes, created_at
            FROM approval_logs
            WHERE doc_type = %s AND doc_id = %s
            ORDER BY id ASC
            """,
            (doc_type, doc_id),
        )
        return cur.fetchall()
