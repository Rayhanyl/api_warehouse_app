"""Skrip bootstrap untuk membuat akun Super Admin pertama (folder_structure.MD).

Cara menjalankan:
    python scripts/create_superadmin.py
    python scripts/create_superadmin.py --username superadmin --email admin@wms.local --password Password123!
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

# Pastikan root proyek berada di sys.path saat dijalankan sebagai `python scripts/create_superadmin.py`
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.core.permissions import ROLE_SUPER_ADMIN
from app.core.security import hash_password
from app.repositories import permission_repo, user_repo
from app.services import audit_service


def bootstrap_superadmin(
    *,
    username: str,
    email: str,
    password: str,
    full_name: str,
    db_url: str | None = None,
) -> dict:
    if len(password) < 8:
        raise ValueError("Password minimal harus terdiri dari 8 karakter.")

    conninfo = db_url or settings.database_url
    with psycopg.connect(conninfo, autocommit=True, row_factory=dict_row) as conn:
        with conn.transaction():
            role = permission_repo.get_role_by_name(conn, ROLE_SUPER_ADMIN)
            if not role:
                raise RuntimeError(
                    "Role 'Super Admin' belum ditemukan. Jalankan `python -m db.migrate` terlebih dahulu."
                )

            existing = user_repo.get_user_by_username(conn, username)
            if existing:
                print(f"[create_superadmin] User '{username}' sudah terdaftar (id={existing['id']}).")
                return existing

            pw_hash = hash_password(password)
            created = user_repo.insert_user(
                conn,
                username=username,
                email=email,
                password_hash=pw_hash,
                full_name=full_name,
                role_id=int(role["id"]),
                is_active=True,
                created_by=None,
            )
            audit_service.record(
                conn,
                user_id=int(created["id"]),
                action="SUPERADMIN_BOOTSTRAPPED",
                entity_type="users",
                entity_id=created["id"],
                new_values={
                    "username": created["username"],
                    "email": created["email"],
                    "role": ROLE_SUPER_ADMIN,
                },
                ip_address="127.0.0.1",
            )
            print(
                f"[create_superadmin] Berhasil membuat Super Admin '{username}' (id={created['id']})."
            )
            return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap akun Super Admin pertama.")
    parser.add_argument(
        "--username",
        default=os.environ.get("SUPERADMIN_USERNAME", "superadmin"),
        help="Username Super Admin (default: superadmin)",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("SUPERADMIN_EMAIL", "superadmin@wms.local"),
        help="Email Super Admin (default: superadmin@wms.local)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("SUPERADMIN_PASSWORD", "Admin12345!"),
        help="Password Super Admin minimal 8 karakter",
    )
    parser.add_argument(
        "--full-name",
        default=os.environ.get("SUPERADMIN_FULL_NAME", "System Super Admin"),
        help="Nama lengkap Super Admin",
    )
    args = parser.parse_args()
    bootstrap_superadmin(
        username=args.username,
        email=args.email,
        password=args.password,
        full_name=args.full_name,
    )


if __name__ == "__main__":
    main()

