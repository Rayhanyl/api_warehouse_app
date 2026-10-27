"""Membuat akun pengembangan untuk setiap role RBAC.

Password dibaca dari environment atau diminta secara tersembunyi melalui prompt.
Script ini idempotent: akun yang sudah ada tidak diubah.

Contoh:
    python scripts/seed_users.py

Environment password yang didukung:
    SEED_SUPER_ADMIN_PASSWORD
    SEED_WAREHOUSE_MANAGER_PASSWORD
    SEED_PURCHASING_STAFF_PASSWORD
    SEED_WAREHOUSE_STAFF_PASSWORD
    SEED_AUDITOR_PASSWORD
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path
import sys
from typing import Any

# Pastikan root proyek berada di sys.path saat dijalankan sebagai script.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.core.permissions import (
    ROLE_AUDITOR,
    ROLE_PURCHASING_STAFF,
    ROLE_SUPER_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_STAFF,
)
from app.core.security import hash_password
from app.repositories import permission_repo, user_repo
from app.services import audit_service


SEED_USERS: tuple[dict[str, str], ...] = (
    {
        "role": ROLE_SUPER_ADMIN,
        "username": "superadmin",
        "email": "superadmin@wms.local",
        "full_name": "System Super Admin",
        "password_env": "SEED_SUPER_ADMIN_PASSWORD",
    },
    {
        "role": ROLE_WAREHOUSE_MANAGER,
        "username": "warehouse.manager",
        "email": "warehouse.manager@wms.local",
        "full_name": "Warehouse Manager",
        "password_env": "SEED_WAREHOUSE_MANAGER_PASSWORD",
    },
    {
        "role": ROLE_PURCHASING_STAFF,
        "username": "purchasing.staff",
        "email": "purchasing.staff@wms.local",
        "full_name": "Purchasing Staff",
        "password_env": "SEED_PURCHASING_STAFF_PASSWORD",
    },
    {
        "role": ROLE_WAREHOUSE_STAFF,
        "username": "warehouse.staff",
        "email": "warehouse.staff@wms.local",
        "full_name": "Warehouse Staff",
        "password_env": "SEED_WAREHOUSE_STAFF_PASSWORD",
    },
    {
        "role": ROLE_AUDITOR,
        "username": "auditor",
        "email": "auditor@wms.local",
        "full_name": "Internal Auditor",
        "password_env": "SEED_AUDITOR_PASSWORD",
    },
)


def _read_password(user: dict[str, str]) -> str:
    password = os.environ.get(user["password_env"])
    if password is None:
        password = getpass.getpass(
            f"Password untuk {user['role']} ({user['username']}): "
        )
    if len(password) < 8:
        raise ValueError(
            f"Password untuk {user['username']} minimal harus terdiri dari 8 karakter."
        )
    return password


def seed_users(db_url: str | None = None) -> list[dict[str, Any]]:
    """Membuat akun yang belum ada dan mengembalikan ringkasan hasilnya."""
    conninfo = db_url or settings.database_url
    results: list[dict[str, Any]] = []

    with psycopg.connect(conninfo, autocommit=True, row_factory=dict_row) as conn:
        with conn.transaction():
            for user in SEED_USERS:
                role = permission_repo.get_role_by_name(conn, user["role"])
                if not role:
                    raise RuntimeError(
                        f"Role '{user['role']}' belum ditemukan. "
                        "Jalankan `python -m db.migrate` terlebih dahulu."
                    )

                existing = user_repo.get_user_by_username(conn, user["username"])
                if existing:
                    if (
                        existing["email"] != user["email"]
                        or existing["role_name"] != user["role"]
                    ):
                        raise RuntimeError(
                            f"User '{user['username']}' sudah ada dengan email atau role berbeda."
                        )
                    results.append(
                        {
                            "username": user["username"],
                            "role": user["role"],
                            "status": "exists",
                            "id": int(existing["id"]),
                        }
                    )
                    continue

                email_owner = user_repo.get_user_by_email(conn, user["email"])
                if email_owner:
                    raise RuntimeError(
                        f"Email '{user['email']}' sudah digunakan oleh "
                        f"user '{email_owner['username']}'."
                    )

                created = user_repo.insert_user(
                    conn,
                    username=user["username"],
                    email=user["email"],
                    password_hash=hash_password(_read_password(user)),
                    full_name=user["full_name"],
                    role_id=int(role["id"]),
                    is_active=True,
                    created_by=None,
                )
                audit_service.record(
                    conn,
                    user_id=int(created["id"]),
                    action="USER_SEEDED",
                    entity_type="users",
                    entity_id=created["id"],
                    new_values={
                        "username": created["username"],
                        "email": created["email"],
                        "role": user["role"],
                    },
                    ip_address="127.0.0.1",
                )
                results.append(
                    {
                        "username": user["username"],
                        "role": user["role"],
                        "status": "created",
                        "id": int(created["id"]),
                    }
                )
    return results


def main() -> None:
    for result in seed_users():
        print(
            f"[seed_users] {result['status']}: "
            f"{result['username']} ({result['role']}, id={result['id']})"
        )


if __name__ == "__main__":
    main()
