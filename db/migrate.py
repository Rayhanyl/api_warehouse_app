"""Runner migrasi SQL forward-only untuk WMS API (PRD 7.5).

Cara menjalankan:
    python -m db.migrate
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _load_dotenv_if_present() -> None:
    """Membaca berkas .env secara sederhana bila variabel lingkungan belum diset."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Hapus komentar inline bila ada
        val_clean = value.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), val_clean)


def get_migration_db_url(override_url: str | None = None) -> str:
    if override_url:
        return override_url
    _load_dotenv_if_present()
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "MIGRATION_DATABASE_URL (atau DATABASE_URL) belum diatur di environment/.env"
        )
    return url


def run_migrations(db_url: str | None = None) -> list[str]:
    """Menjalankan seluruh berkas .sql di db/migrations/ yang belum tercatat di schema_migrations.

    Mengembalikan daftar nama berkas migrasi yang baru diterapkan pada pemanggilan ini.
    """
    conninfo = get_migration_db_url(db_url)
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    applied_now: list[str] = []

    with psycopg.connect(conninfo, autocommit=True, row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(100) NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT pk_schema_migrations PRIMARY KEY (version)
                );
                """
            )

        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        already_applied = {row["version"] for row in rows}

        for sql_file in sql_files:
            version = sql_file.name
            if version in already_applied:
                continue

            sql_content = sql_file.read_text(encoding="utf-8")
            if not sql_content.strip():
                continue

            with conn.transaction():
                conn.execute(sql_content)
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
            applied_now.append(version)
            print(f"[migrate] Applied: {version}")

    if not applied_now:
        print("[migrate] Skema sudah mutakhir (tidak ada migrasi baru).")

    return applied_now


if __name__ == "__main__":
    try:
        run_migrations()
    except Exception as exc:
        print(f"[migrate] Gagal menjalankan migrasi: {exc}", file=sys.stderr)
        sys.exit(1)

