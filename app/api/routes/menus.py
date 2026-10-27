"""Routes Menu Navigasi Dinamis (FR-01, PRD Lampiran A & C)."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from psycopg import Connection

from app.api.deps import get_client_ip, get_current_user
from app.core.database import get_conn
from app.core.permissions import USER_MANAGE, require_permission
from app.schemas.common import Page
from app.schemas.menu import MenuCreate, MenuOut, MenuTreeOut, MenuUpdate
from app.services import menu_service

router = APIRouter(prefix="/menus", tags=["Menus"])


@router.get("/my-menu", response_model=list[MenuTreeOut])
def get_my_menu(
    actor: dict[str, Any] = Depends(get_current_user),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> list[MenuTreeOut]:
    """Mengambil pohon menu navigasi yang berhak diakses oleh pengguna yang sedang login."""
    tree = menu_service.get_my_menu_tree(conn, actor=actor)
    return [MenuTreeOut(**node) for node in tree]


@router.get("", response_model=Page[MenuOut])
def list_menus(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    is_active: bool | None = Query(default=None),
    parent_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[MenuOut]:
    page = menu_service.list_menus(
        conn,
        limit=limit,
        offset=offset,
        is_active=is_active,
        parent_id=parent_id,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[MenuOut](**page)


@router.post("", response_model=MenuOut, status_code=status.HTTP_201_CREATED)
def create_menu(
    payload: MenuCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> MenuOut:
    created = menu_service.create_menu(
        conn,
        actor=actor,
        code=payload.code,
        name=payload.name,
        path=payload.path,
        icon=payload.icon,
        parent_id=payload.parent_id,
        sort_order=payload.sort_order,
        permission_id=payload.permission_id,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return MenuOut(**created)


@router.get("/{menu_id}", response_model=MenuOut)
def get_menu(
    menu_id: int,
    _actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> MenuOut:
    menu = menu_service.get_menu(conn, menu_id)
    return MenuOut(**menu)


@router.patch("/{menu_id}", response_model=MenuOut)
def update_menu(
    menu_id: int,
    payload: MenuUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> MenuOut:
    updated = menu_service.update_menu(
        conn,
        actor=actor,
        menu_id=menu_id,
        code=payload.code,
        name=payload.name,
        path=payload.path,
        icon=payload.icon,
        parent_id=payload.parent_id,
        clear_parent=payload.clear_parent,
        sort_order=payload.sort_order,
        permission_id=payload.permission_id,
        clear_permission=payload.clear_permission,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return MenuOut(**updated)

