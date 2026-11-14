"""Repository SQL untuk tabel audit_logs (append-only, FR-09, PRD 6.4, & Tahap 14)."""

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
    "status": "a.status",
    "ip_address": "a.ip_address",
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
    status: str = "SUCCESS",
    details: dict[str, Any] | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
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
            status,
            details,
            ip_address,
            user_agent,
            request_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING
            id,
            user_id,
            action,
            entity_type,
            entity_id,
            old_values,
            new_values,
            status,
            details,
            ip_address,
            user_agent,
            request_id,
            created_at
        """,
        (
            user_id,
            action,
            entity_type,
            str(entity_id) if entity_id is not None else None,
            Jsonb(old_values) if old_values is not None else None,
            Jsonb(new_values) if new_values is not None else None,
            status,
            Jsonb(details) if details is not None else None,
            ip_address,
            user_agent,
            request_id,
        ),
    ).fetchone()
    assert row is not None
    return row


def insert_audit_logs_batch(
    conn: Connection[dict[str, Any]], events: list[dict[str, Any]]
) -> None:
    """Menyisipkan sekumpulan event audit tanpa mengubah baris append-only."""
    if not events:
        return
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO audit_logs (
                user_id,
                action,
                entity_type,
                entity_id,
                old_values,
                new_values,
                status,
                details,
                ip_address,
                user_agent,
                request_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    event["user_id"],
                    event["action"],
                    event["entity_type"],
                    str(event["entity_id"])
                    if event["entity_id"] is not None
                    else None,
                    Jsonb(event["old_values"])
                    if event["old_values"] is not None
                    else None,
                    Jsonb(event["new_values"])
                    if event["new_values"] is not None
                    else None,
                    event.get("status", "SUCCESS"),
                    Jsonb(event["details"])
                    if event.get("details") is not None
                    else None,
                    event["ip_address"],
                    event.get("user_agent"),
                    event.get("request_id"),
                )
                for event in events
            ],
        )


def list_audit_logs(
    conn: Connection[dict[str, Any]],
    *,
    limit: int,
    offset: int,
    user_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
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
    if status is not None:
        conditions.append("a.status = %s")
        params.append(status)
    if date_from is not None:
        conditions.append("a.created_at >= %s")
        params.append(date_from)
    if date_to is not None:
        conditions.append("a.created_at <= %s")
        params.append(date_to)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            "(a.action ILIKE %s OR a.entity_type ILIKE %s OR COALESCE(a.entity_id, '') ILIKE %s OR COALESCE(u.username, '') ILIKE %s OR COALESCE(a.ip_address, '') ILIKE %s OR COALESCE(a.request_id, '') ILIKE %s)"
        )
        params.extend([pattern, pattern, pattern, pattern, pattern, pattern])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_clause = build_order_by(sort_by, sort_dir, AUDIT_SORT_COLUMNS, "id", "DESC")
    join_users_in_count = "LEFT JOIN users u ON u.id = a.user_id" if search else ""

    count_row = conn.execute(
        f"SELECT COUNT(*) AS total FROM audit_logs a {join_users_in_count} {where_clause}",
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
            a.status,
            a.details,
            a.ip_address,
            a.user_agent,
            a.request_id,
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
