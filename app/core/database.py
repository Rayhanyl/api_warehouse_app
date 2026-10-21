"""Koneksi pool PostgreSQL sinkron (psycopg 3) dan dependency get_conn."""

from collections.abc import Generator
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import settings

pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=2,
    max_size=10,
    kwargs={"autocommit": True, "row_factory": dict_row},
    open=False,  # dibuka dan ditutup pada lifespan di app/main.py
)


def open_pool(conninfo: str | None = None) -> None:
    """Membuka connection pool (dan membuat instance baru bila pool sebelumnya sudah ditutup)."""
    global pool
    target_conninfo = conninfo or pool.conninfo
    if pool.closed or (conninfo is not None and conninfo != pool.conninfo):
        pool = ConnectionPool(
            conninfo=target_conninfo,
            min_size=2,
            max_size=10,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=False,
        )
    pool.open(wait=True)


def close_pool() -> None:
    """Menutup connection pool bila sedang terbuka."""
    if not pool.closed:
        pool.close()


def get_conn() -> Generator[Connection[dict[str, Any]], None, None]:
    """Dependency FastAPI untuk menyediakan satu koneksi dari pool per request."""
    with pool.connection() as conn:
        yield conn


def check_db_health(conn: Connection[dict[str, Any]]) -> bool:
    """Memeriksa konektivitas database menggunakan koneksi pool."""
    row = conn.execute("SELECT 1 AS ok").fetchone()
    return bool(row and row.get("ok") == 1)
