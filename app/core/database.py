"""Koneksi pool PostgreSQL sinkron (psycopg 3) dan dependency get_conn."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from psycopg import Connection, Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from app.core.config import settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"

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
    """Memeriksa konektivitas database menggunakan koneksi yang diberikan."""
    try:
        row = conn.execute("SELECT 1 AS ok").fetchone()
        return bool(row and row.get("ok") == 1)
    except PsycopgError:
        return False


def check_pool_health() -> bool:
    """Memeriksa kesehatan koneksi pool secara aman tanpa melempar exception saat DB mati."""
    try:
        if pool.closed:
            return False
        with pool.connection(timeout=2.0) as conn:
            return check_db_health(conn)
    except (PsycopgError, PoolTimeout, OSError):
        return False


def list_pending_migrations(conn: Connection[dict[str, Any]]) -> list[str]:
    """Mengembalikan daftar nama berkas migrasi SQL yang belum diterapkan pada database."""
    if not MIGRATIONS_DIR.is_dir():
        return []
    migration_files = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        return []

    table_row = conn.execute(
        "SELECT to_regclass('public.schema_migrations') IS NOT NULL AS exists"
    ).fetchone()
    if not table_row or not table_row["exists"]:
        return migration_files

    applied_rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    applied_versions = {row["version"] for row in applied_rows}
    return [name for name in migration_files if name not in applied_versions]


def check_schema_health() -> tuple[bool, list[str]]:
    """Memeriksa kesiapan DB sekaligus mendeteksi migrasi SQL yang belum dijalankan."""
    try:
        if pool.closed:
            return False, []
        with pool.connection(timeout=2.0) as conn:
            if not check_db_health(conn):
                return False, []
            return True, list_pending_migrations(conn)
    except (PsycopgError, PoolTimeout, OSError):
        return False, []
