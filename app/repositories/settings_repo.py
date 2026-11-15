"""Repository konfigurasi sistem (app_settings, Tahap 34)."""

from typing import Any

from psycopg import Connection

KEY_PO_L2_APPROVAL_THRESHOLD = "po_l2_approval_threshold"


def get_setting(conn: Connection[dict[str, Any]], key: str) -> dict[str, Any] | None:
    """Membaca satu pengaturan berdasarkan kunci uniknya."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.key,
                s.value,
                s.description,
                s.updated_by,
                u.full_name AS updated_by_name,
                s.updated_at
            FROM app_settings s
            LEFT JOIN users u ON u.id = s.updated_by
            WHERE s.key = %s
            """,
            (key,),
        )
        return cur.fetchone()


def upsert_setting(
    conn: Connection[dict[str, Any]],
    *,
    key: str,
    value: str,
    description: str | None = None,
    updated_by: int | None = None,
) -> dict[str, Any]:
    """Menyimpan atau memperbarui pengaturan sistem secara atomik."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_settings (key, value, description, updated_by, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                description = COALESCE(EXCLUDED.description, app_settings.description),
                updated_by = EXCLUDED.updated_by,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value, description, updated_by),
        )
    saved = get_setting(conn, key)
    if saved is None:
        raise RuntimeError(f"Gagal membaca kembali app_settings untuk key '{key}'.")
    return saved
