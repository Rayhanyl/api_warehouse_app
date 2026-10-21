"""Repository SQL untuk tabel audit_logs (append-only, FR-09 & PRD 6.4)."""

from datetime import datetime
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.utils.pagination import build_order_by

AUDIT_SORT_COLUMNS: dict[str, str] = {
    "id": "a.id",
    "created_at": "a.created_at",
    "action": "a.action",
    "entity_type": "a.entity_type",
}


def insert_audit_log(
    conn: Connection[dict[str, Any]],
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    old_values: dict[str, Any] | None,
    new_values: dict[str, Any] | None,
    ip_address: str | None,
) -> dict[str, Any]:
    """Menyisipkan satu baris jejak audit ke tabel audit_logs."""
    row = conn.execute(
        """
        INSERT INTO audit_logs (
            user_id,
            action,
            entity_type,
            entity_id,
            old_values,
            new_values,
            ip_address
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING
            id,
            user_id,
            action,
            entity_type,
            entity_id,
            old_values,
            new_values,
            ip_address,
            created_at
        """,
        (
            user_id,
            action,
            entity_type,
            str(entity_id) if entity_id is not None else None,
            Jsonb(old_values) if old_values is not None else None,
            Jsonb(new_values) if new_values is not None else None,
            ip_address,
        ),
    ).fetchone()
    assert row is not None
    return row


def list_audit_logs(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    user_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Membaca daftar audit_logs dengan filter dan pagination."""
    conditions: list[str] = []
    params: list[Any] = []

    if user_id is not None:
        conditions.append("a.user_id = %s")
        params.append(user_id)
    if action is not None:
        conditions.append("a.action = %s")
        params.append(action)
    if entity_type is not None:
        conditions.append("a.entity_type = %s")
        params.append(entity_type)
    if entity_id is not None:
        conditions.append("a.entity_id = %s")
        params.append(entity_id)
    if date_from is not None:
        conditions.append("a.created_at >= %s")
        params.append(date_from)
    if date_to is not None:
        conditions.append("a.created_at <= %s")
        params.append(date_to)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_clause = build_order_by(sort_by, sort_dir, AUDIT_SORT_COLUMNS, "id", "DESC")

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM audit_logs a {where_clause}",
        params,
    ).fetchone()
    total = int(count_row["total"]) if count_row else 0

    rows = conn.execute(
        f"""
        SELECT
            a.id,
            a.user_id,
            u.username,
            a.action,
            a.entity_type,
            a.entity_id,
            a.old_values,
            a.new_values,
            a.ip_address,
            a.created_at
        FROM audit_logs a
        LEFT JOIN users u ON u.id = a.user_id
        {where_clause}
        ORDER BY {order_clause}
        LIMIT %s OFFSET %s
        """,
        [*params, limit, offset],
    ).fetchall()

    return list(rows), total

