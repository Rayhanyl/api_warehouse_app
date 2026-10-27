"""Service logika bisnis untuk Menu Navigasi Dinamis (FR-01, PRD Lampiran A & C)."""

from typing import Any

from psycopg import Connection

from app.core.exceptions import (
    DuplicateError,
    EntityInUse,
    InactiveReferenceError,
    NotFoundError,
    ValidationDomainError,
)
from app.repositories import menu_repo
from app.services import audit_service
from app.utils.pagination import build_order_by, normalize_pagination

MENU_SORT_COLUMNS: dict[str, str] = {
    "id": "m.id",
    "code": "m.code",
    "name": "m.name",
    "sort_order": "m.sort_order",
    "created_at": "m.created_at",
}


def get_my_menu_tree(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
) -> list[dict[str, Any]]:
    """Menyusun pohon menu aktif yang berhak dilihat oleh pengguna aktif berdasarkan daftar permission-nya.

    Aturan penyaringan pohon:
    1. Hanya menu berstatus `is_active = TRUE` yang dipertimbangkan.
    2. Jika suatu menu memiliki `permission_code` (tidak NULL), pengguna wajib memiliki kode izin tersebut
       di dalam `actor["permissions"]`.
    3. Jika suatu menu merupakan menu induk (memiliki anak di database) dan `permission_code IS NULL`
       (seperti grup 'Master Data' atau 'Administrasi & Keamanan'), menu induk tersebut hanya ditampilkan
       apabila memiliki minimal satu submenu anak yang berhak diakses oleh pengguna.
    4. Jika suatu menu adalah menu mandiri/daun (tidak memiliki anak di database) dan `permission_code IS NULL`
       (seperti 'Dashboard'), menu tersebut ditampilkan untuk seluruh pengguna terautentikasi.
    """
    user_permissions: set[str] = set(actor.get("permissions", []))
    active_rows = menu_repo.list_active_menus_ordered(conn)

    children_by_parent: dict[int | None, list[dict[str, Any]]] = {}
    has_db_children: set[int] = set()

    for row in active_rows:
        pid = row["parent_id"]
        children_by_parent.setdefault(pid, []).append(row)
        if pid is not None:
            has_db_children.add(int(pid))

    def _build_subtree(
        parent_id: int | None, visited: set[int]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for node in children_by_parent.get(parent_id, []):
            node_id = int(node["id"])
            if node_id in visited:
                continue

            req_perm = node.get("permission_code")
            if req_perm is not None and req_perm not in user_permissions:
                continue

            visible_children = _build_subtree(node_id, visited | {node_id})

            # Jika menu adalah grup induk tanpa permission khusus dan seluruh anaknya terfilter habis, sembunyikan grup
            if (
                node_id in has_db_children
                and req_perm is None
                and not visible_children
            ):
                continue

            result.append(
                {
                    "id": node_id,
                    "code": node["code"],
                    "name": node["name"],
                    "path": node["path"],
                    "icon": node["icon"],
                    "parent_id": node["parent_id"],
                    "sort_order": int(node["sort_order"]),
                    "permission_code": req_perm,
                    "is_active": True,
                    "is_visible": True,
                    "menu_type": "group" if node_id in has_db_children else "item",
                    "children": visible_children,
                }
            )
        return result

    return _build_subtree(None, set())


def list_menus(
    conn: Connection[dict[str, Any]],
    *,
    limit: int = 50,
    offset: int = 0,
    is_active: bool | None = None,
    parent_id: int | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> dict[str, Any]:
    norm_limit, norm_offset = normalize_pagination(limit, offset)
    order_by_sql = build_order_by(
        sort_by=sort_by,
        sort_dir=sort_dir,
        allowed_columns=MENU_SORT_COLUMNS,
        default_column="sort_order",
        default_dir="ASC",
    )
    items, total = menu_repo.list_menus(
        conn,
        limit=norm_limit,
        offset=norm_offset,
        is_active=is_active,
        parent_id=parent_id,
        search=search,
        order_by_sql=f"{order_by_sql}, m.id ASC",
    )
    return {
        "items": items,
        "total": total,
        "limit": norm_limit,
        "offset": norm_offset,
    }


def get_menu(conn: Connection[dict[str, Any]], menu_id: int) -> dict[str, Any]:
    menu = menu_repo.get_menu_by_id(conn, menu_id)
    if not menu:
        raise NotFoundError(
            "Menu tidak ditemukan.",
            details={"menu_id": menu_id},
        )
    return menu


def _resolve_permission_id(
    conn: Connection[dict[str, Any]],
    *,
    permission_id: int | None,
) -> int | None:
    if permission_id is not None:
        perm = menu_repo.get_permission_by_id(conn, permission_id)
        if not perm:
            raise NotFoundError(
                "Permission tidak ditemukan.",
                details={"permission_id": permission_id},
            )
        return int(perm["id"])

    return None


def _validate_parent_menu(
    conn: Connection[dict[str, Any]],
    *,
    parent_id: int | None,
    current_menu_id: int | None = None,
) -> None:
    if parent_id is None:
        return

    if current_menu_id is not None and parent_id == current_menu_id:
        raise ValidationDomainError(
            "Menu tidak boleh menunjuk dirinya sendiri sebagai menu induk (parent_id).",
            details={"menu_id": current_menu_id, "parent_id": parent_id},
        )

    parent = menu_repo.get_menu_by_id(conn, parent_id)
    if not parent:
        raise NotFoundError(
            "Menu induk (parent_id) tidak ditemukan.",
            details={"parent_id": parent_id},
        )
    if not parent["is_active"]:
        raise InactiveReferenceError(
            "Menu induk (parent_id) berstatus tidak aktif.",
            details={"parent_id": parent_id},
        )

    # Cegah siklus hierarki (circular reference)
    if current_menu_id is not None:
        visited: set[int] = {current_menu_id}
        cursor_parent_id = parent["parent_id"]
        while cursor_parent_id is not None:
            if int(cursor_parent_id) in visited:
                raise ValidationDomainError(
                    "Terdeteksi siklus hierarki (circular parent reference) pada menu.",
                    details={"menu_id": current_menu_id, "parent_id": parent_id},
                )
            visited.add(int(cursor_parent_id))
            ancestor = menu_repo.get_menu_by_id(conn, int(cursor_parent_id))
            cursor_parent_id = ancestor["parent_id"] if ancestor else None


def create_menu(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    code: str,
    name: str,
    path: str,
    icon: str | None = None,
    parent_id: int | None = None,
    sort_order: int = 0,
    permission_id: int | None = None,
    is_active: bool = True,
    ip_address: str | None = None,
) -> dict[str, Any]:
    clean_code = code.strip()
    clean_name = name.strip()
    clean_path = path.strip()
    clean_icon = icon.strip() if icon and icon.strip() else None

    if not clean_code:
        raise ValidationDomainError(
            "Kode menu tidak boleh kosong.",
            details={"field": "code"},
        )
    if not clean_name:
        raise ValidationDomainError(
            "Nama menu tidak boleh kosong.",
            details={"field": "name"},
        )
    if not clean_path or not clean_path.startswith("/"):
        raise ValidationDomainError(
            "Path menu wajib diawali dengan karakter '/'.",
            details={"field": "path", "value": clean_path},
        )

    with conn.transaction():
        existing = menu_repo.get_menu_by_code(conn, clean_code)
        if existing:
            raise DuplicateError(
                f"Menu dengan kode '{clean_code}' sudah terdaftar.",
                details={"field": "code", "value": clean_code},
            )

        _validate_parent_menu(conn, parent_id=parent_id)
        resolved_perm_id = _resolve_permission_id(
            conn,
            permission_id=permission_id,
        )

        created = menu_repo.insert_menu(
            conn,
            code=clean_code,
            name=clean_name,
            path=clean_path,
            icon=clean_icon,
            parent_id=parent_id,
            sort_order=sort_order,
            permission_id=resolved_perm_id,
            is_active=is_active,
            created_by=int(actor["id"]),
        )
        if created is None:
            raise DuplicateError(
                f"Menu dengan kode '{clean_code}' sudah terdaftar.",
                details={"field": "code", "value": clean_code},
            )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action="MENU_CREATED",
            entity_type="menus",
            entity_id=created["id"],
            old_values=None,
            new_values=created,
            ip_address=ip_address,
        )
        return created


def update_menu(
    conn: Connection[dict[str, Any]],
    *,
    actor: dict[str, Any],
    menu_id: int,
    code: str | None = None,
    name: str | None = None,
    path: str | None = None,
    icon: str | None = None,
    parent_id: int | None = None,
    clear_parent: bool = False,
    sort_order: int | None = None,
    permission_id: int | None = None,
    clear_permission: bool = False,
    is_active: bool | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    with conn.transaction():
        locked = menu_repo.lock_menu_by_id(conn, menu_id)
        if not locked:
            raise NotFoundError(
                "Menu tidak ditemukan.",
                details={"menu_id": menu_id},
            )
        old_snapshot = menu_repo.get_menu_by_id(conn, menu_id)

        new_code = code.strip() if code is not None else locked["code"]
        new_name = name.strip() if name is not None else locked["name"]
        new_path = path.strip() if path is not None else locked["path"]

        if not new_code:
            raise ValidationDomainError(
                "Kode menu tidak boleh kosong.",
                details={"field": "code"},
            )
        if not new_name:
            raise ValidationDomainError(
                "Nama menu tidak boleh kosong.",
                details={"field": "name"},
            )
        if not new_path or not new_path.startswith("/"):
            raise ValidationDomainError(
                "Path menu wajib diawali dengan karakter '/'.",
                details={"field": "path", "value": new_path},
            )

        if new_code != locked["code"]:
            dup = menu_repo.get_menu_by_code(conn, new_code)
            if dup and int(dup["id"]) != menu_id:
                raise DuplicateError(
                    f"Menu dengan kode '{new_code}' sudah terdaftar.",
                    details={"field": "code", "value": new_code},
                )

        if icon is not None:
            new_icon = icon.strip() if icon.strip() else None
        else:
            new_icon = locked["icon"]

        if clear_parent:
            new_parent_id = None
        elif parent_id is not None:
            new_parent_id = parent_id
        else:
            new_parent_id = locked["parent_id"]

        _validate_parent_menu(
            conn, parent_id=new_parent_id, current_menu_id=menu_id
        )

        if clear_permission:
            new_perm_id = None
        elif permission_id is not None:
            new_perm_id = _resolve_permission_id(
                conn,
                permission_id=permission_id,
            )
        else:
            new_perm_id = locked["permission_id"]

        new_sort_order = (
            sort_order if sort_order is not None else int(locked["sort_order"])
        )
        new_is_active = (
            is_active if is_active is not None else bool(locked["is_active"])
        )

        # Cegah penonaktifan menu induk yang masih memiliki submenu aktif
        if locked["is_active"] and not new_is_active:
            if menu_repo.has_active_child_menus(conn, menu_id):
                raise EntityInUse(
                    "Menu induk tidak dapat dinonaktifkan karena masih memiliki submenu yang aktif.",
                    details={"menu_id": menu_id},
                )

        updated = menu_repo.update_menu(
            conn,
            menu_id,
            code=new_code,
            name=new_name,
            path=new_path,
            icon=new_icon,
            parent_id=new_parent_id,
            sort_order=new_sort_order,
            permission_id=new_perm_id,
            is_active=new_is_active,
        )

        action_name = (
            "MENU_DEACTIVATED"
            if locked["is_active"] and not new_is_active
            else "MENU_UPDATED"
        )
        audit_service.record(
            conn,
            user_id=int(actor["id"]),
            action=action_name,
            entity_type="menus",
            entity_id=menu_id,
            old_values=old_snapshot,
            new_values=updated,
            ip_address=ip_address,
        )
        return updated
