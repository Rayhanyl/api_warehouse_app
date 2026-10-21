"""Service Manajemen Pengguna, Role/Permission, dan Penugasan Gudang (Bagian 3 PRD, FR-01, FR-09)."""

from datetime import datetime, timezone
from typing import Any

from psycopg import Connection

from app.core.exceptions import (
    DuplicateError,
    InactiveReferenceError,
    NotFoundError,
    ValidationDomainError,
)
from app.core.security import hash_password
from app.repositories import permission_repo, token_repo, user_repo
from app.services import audit_service
from app.utils.pagination import normalize_pagination


def _public_user_snapshot(user: dict[str, Any]) -> dict[str, Any]:
    """Mengambil representasi aman atribut pengguna untuk pencatatan Audit Log."""
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role_id": user["role_id"],
        "role_name": user.get("role_name"),
        "is_active": user["is_active"],
        "warehouse_ids": user.get("warehouse_ids", []),
    }


def list_users(
    conn: Connection[dict[str, Any]],
    *,
    limit: int = 50,
    offset: int = 0,
    role_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    """Mengambil daftar pengguna terpaginasi."""
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    items, total = user_repo.list_users(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        role_id=role_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def get_user(conn: Connection[dict[str, Any]], user_id: int) -> dict[str, Any]:
    """Mengambil detail seorang pengguna beserta permission dan gudang yang ditugaskan."""
    user = user_repo.get_user_auth_context(conn, user_id)
    if not user:
        raise NotFoundError(
            "Pengguna tidak ditemukan.",
            details={"user_id": user_id},
        )
    return user


def create_user(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    username: str,
    email: str,
    password: str,
    full_name: str,
    role_id: int,
    is_active: bool = True,
    warehouse_ids: list[int] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Membuat akun pengguna baru, menetapkan penugasan gudang bila ada, dan menulis Audit Log."""
    if len(password) < 8:
        raise ValidationDomainError("Kata sandi minimal harus terdiri dari 8 karakter.")

    clean_username = username.strip()
    clean_email = email.strip().lower()
    clean_name = full_name.strip()

    with conn.transaction():
        if user_repo.get_user_by_username(conn, clean_username):
            raise DuplicateError(
                f"Username '{clean_username}' sudah digunakan.",
                details={"field": "username", "value": clean_username},
            )
        if user_repo.get_user_by_email(conn, clean_email):
            raise DuplicateError(
                f"Email '{clean_email}' sudah digunakan.",
                details={"field": "email", "value": clean_email},
            )

        role = permission_repo.get_role_by_id(conn, role_id)
        if not role:
            raise NotFoundError(
                "Peran (role) tidak ditemukan.",
                details={"role_id": role_id},
            )

        if warehouse_ids:
            _validate_warehouses_exist_and_active(conn, warehouse_ids)

        pw_hash = hash_password(password)
        created = user_repo.insert_user(
            conn,
            username=clean_username,
            email=clean_email,
            password_hash=pw_hash,
            full_name=clean_name,
            role_id=role_id,
            is_active=is_active,
            created_by=int(actor["id"]),
        )

        if warehouse_ids:
            permission_repo.update_user_warehouses(
                conn,
                user_id=int(created["id"]),
                warehouse_ids=warehouse_ids,
                actor_id=int(actor["id"]),
            )
            created = user_repo.get_user_auth_context(conn, int(created["id"]))
            assert created is not None

        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="USER_CREATED",
            entity_type="users",
            entity_id=created["id"],
            new_values=_public_user_snapshot(created),
            ip_address=ip_address,
        )
        return created


def update_user(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    user_id: int,
    email: str | None = None,
    full_name: str | None = None,
    role_id: int | None = None,
    is_active: bool | None = None,
    password: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Memperbarui data pengguna; mencabut seluruh Refresh Token bila dinonaktifkan atau ganti password (FR-01)."""
    if password is not None and len(password) < 8:
        raise ValidationDomainError("Kata sandi minimal harus terdiri dari 8 karakter.")

    now = datetime.now(timezone.utc)
    actor_id = int(actor["id"])

    with conn.transaction():
        locked = user_repo.lock_user_by_id(conn, user_id)
        if not locked:
            raise NotFoundError(
                "Pengguna tidak ditemukan.",
                details={"user_id": user_id},
            )
        before_ctx = user_repo.get_user_auth_context(conn, user_id)
        assert before_ctx is not None

        new_email = email.strip().lower() if email is not None else before_ctx["email"]
        if new_email != before_ctx["email"]:
            existing_email = user_repo.get_user_by_email(conn, new_email)
            if existing_email and int(existing_email["id"]) != user_id:
                raise DuplicateError(
                    f"Email '{new_email}' sudah digunakan.",
                    details={"field": "email", "value": new_email},
                )

        new_full_name = (
            full_name.strip() if full_name is not None else before_ctx["full_name"]
        )
        new_role_id = int(role_id) if role_id is not None else int(before_ctx["role_id"])
        if new_role_id != int(before_ctx["role_id"]):
            role = permission_repo.get_role_by_id(conn, new_role_id)
            if not role:
                raise NotFoundError(
                    "Peran (role) tidak ditemukan.",
                    details={"role_id": new_role_id},
                )

        new_is_active = (
            bool(is_active) if is_active is not None else bool(before_ctx["is_active"])
        )

        updated = user_repo.update_user(
            conn,
            user_id,
            email=new_email,
            full_name=new_full_name,
            role_id=new_role_id,
            is_active=new_is_active,
        )

        if password is not None:
            user_repo.update_user_password(
                conn, user_id, password_hash=hash_password(password)
            )

        if (before_ctx["is_active"] and not new_is_active) or password is not None:
            token_repo.update_revoke_all_user_tokens(conn, user_id, revoked_at=now)

        audit_service.record(
            conn,
            user_id=actor_id,
            action="USER_DEACTIVATED"
            if (before_ctx["is_active"] and not new_is_active)
            else "USER_UPDATED",
            entity_type="users",
            entity_id=user_id,
            old_values=_public_user_snapshot(before_ctx),
            new_values=_public_user_snapshot(updated),
            ip_address=ip_address,
        )
        return updated


def set_user_warehouses(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    user_id: int,
    warehouse_ids: list[int],
    ip_address: str | None = None,
) -> list[dict[str, Any]]:
    """Mengatur daftar gudang yang ditugaskan kepada seorang pengguna (PRD 3.2, hanya Super Admin / user:manage)."""
    actor_id = int(actor["id"])
    clean_ids = sorted({int(wid) for wid in warehouse_ids})

    with conn.transaction():
        locked = user_repo.lock_user_by_id(conn, user_id)
        if not locked:
            raise NotFoundError(
                "Pengguna tidak ditemukan.",
                details={"user_id": user_id},
            )

        _validate_warehouses_exist_and_active(conn, clean_ids)

        old_ids = permission_repo.get_user_warehouse_ids(conn, user_id)
        new_ids = permission_repo.update_user_warehouses(
            conn,
            user_id=user_id,
            warehouse_ids=clean_ids,
            actor_id=actor_id,
        )
        audit_service.record(
            conn,
            user_id=actor_id,
            action="USER_WAREHOUSES_UPDATED",
            entity_type="user_warehouses",
            entity_id=user_id,
            old_values={"user_id": user_id, "warehouse_ids": old_ids},
            new_values={"user_id": user_id, "warehouse_ids": new_ids},
            ip_address=ip_address,
        )
        return permission_repo.list_user_warehouses_detail(conn, user_id)


def list_user_warehouses(
    conn: Connection[dict[str, Any]], user_id: int
) -> list[dict[str, Any]]:
    """Mengambil daftar gudang yang ditugaskan kepada seorang pengguna."""
    user = user_repo.get_user_by_id(conn, user_id)
    if not user:
        raise NotFoundError(
            "Pengguna tidak ditemukan.",
            details={"user_id": user_id},
        )
    return permission_repo.list_user_warehouses_detail(conn, user_id)


def list_roles(conn: Connection[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mengambil seluruh peran beserta daftar kode permission-nya."""
    return permission_repo.list_roles(conn)


def list_permissions(conn: Connection[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mengambil seluruh kode permission yang tersedia di sistem."""
    return permission_repo.list_permissions(conn)


def set_role_permissions(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    role_id: int,
    permission_codes: list[str],
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Memperbarui pemetaan permission untuk suatu peran dan mencatat Audit Log."""
    actor_id = int(actor["id"])
    unique_codes = sorted({c.strip() for c in permission_codes if c.strip()})

    with conn.transaction():
        role = permission_repo.get_role_by_id(conn, role_id)
        if not role:
            raise NotFoundError(
                "Peran (role) tidak ditemukan.",
                details={"role_id": role_id},
            )

        found_perms = permission_repo.get_permissions_by_codes(conn, unique_codes)
        found_codes = {r["code"] for r in found_perms}
        missing_codes = sorted(set(unique_codes) - found_codes)
        if missing_codes:
            raise ValidationDomainError(
                "Terdapat kode permission yang tidak terdaftar di sistem.",
                details={"unknown_permissions": missing_codes},
            )

        old_perms = list(role.get("permissions", []))
        permission_repo.update_role_permissions(
            conn,
            role_id=role_id,
            permission_ids=[int(r["id"]) for r in found_perms],
        )
        updated_role = permission_repo.get_role_by_id(conn, role_id)
        assert updated_role is not None

        audit_service.record(
            conn,
            user_id=actor_id,
            action="ROLE_PERMISSIONS_UPDATED",
            entity_type="roles",
            entity_id=role_id,
            old_values={"role_name": role["name"], "permissions": old_perms},
            new_values={
                "role_name": updated_role["name"],
                "permissions": list(updated_role.get("permissions", [])),
            },
            ip_address=ip_address,
        )
        return updated_role


def _validate_warehouses_exist_and_active(
    conn: Connection[dict[str, Any]], warehouse_ids: list[int]
) -> None:
    """Memastikan seluruh warehouse_id yang akan ditugaskan benar-benar ada dan berstatus aktif."""
    if not warehouse_ids:
        return
    rows = permission_repo.get_existing_warehouses_by_ids(conn, warehouse_ids)
    found_map = {int(r["id"]): r for r in rows}
    missing = [wid for wid in warehouse_ids if wid not in found_map]
    if missing:
        raise NotFoundError(
            "Gudang tidak ditemukan.",
            details={"missing_warehouse_ids": missing},
        )
    inactive = [wid for wid, row in found_map.items() if not row["is_active"]]
    if inactive:
        raise InactiveReferenceError(
            "Gudang yang tidak aktif tidak dapat ditugaskan kepada pengguna.",
            details={"inactive_warehouse_ids": inactive},
        )

