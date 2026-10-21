"""Routes Manajemen Pengguna, Role/Permission, dan Penugasan Gudang (Bagian 3 PRD, user:manage)."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from psycopg import Connection

from app.api.deps import get_client_ip
from app.core.database import get_conn
from app.core.permissions import USER_MANAGE, require_permission
from app.schemas.common import Page
from app.schemas.user import (
    PermissionOut,
    RoleOut,
    RolePermissionSet,
    UserCreate,
    UserOut,
    UserUpdate,
    UserWarehouseOut,
    UserWarehouseSet,
)
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users & RBAC"])


@router.get("", response_model=Page[UserOut])
def list_users(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    role_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[UserOut]:
    page = user_service.list_users(
        conn,
        limit=limit,
        offset=offset,
        role_id=role_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[UserOut](**page)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> UserOut:
    created = user_service.create_user(
        conn,
        actor=actor,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role_id=payload.role_id,
        is_active=payload.is_active,
        warehouse_ids=payload.warehouse_ids,
        ip_address=get_client_ip(request),
    )
    return UserOut(**created)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    _actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> list[RoleOut]:
    roles = user_service.list_roles(conn)
    return [RoleOut(**r) for r in roles]


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(
    _actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> list[PermissionOut]:
    perms = user_service.list_permissions(conn)
    return [PermissionOut(**p) for p in perms]


@router.put("/roles/{role_id}/permissions", response_model=RoleOut)
def set_role_permissions(
    role_id: int,
    payload: RolePermissionSet,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> RoleOut:
    updated = user_service.set_role_permissions(
        conn,
        actor=actor,
        role_id=role_id,
        permission_codes=payload.permissions,
        ip_address=get_client_ip(request),
    )
    return RoleOut(**updated)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    _actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> UserOut:
    user = user_service.get_user(conn, user_id)
    return UserOut(**user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> UserOut:
    updated = user_service.update_user(
        conn,
        actor=actor,
        user_id=user_id,
        email=payload.email,
        full_name=payload.full_name,
        role_id=payload.role_id,
        is_active=payload.is_active,
        password=payload.password,
        ip_address=get_client_ip(request),
    )
    return UserOut(**updated)


@router.get("/{user_id}/warehouses", response_model=list[UserWarehouseOut])
def list_user_warehouses(
    user_id: int,
    _actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> list[UserWarehouseOut]:
    items = user_service.list_user_warehouses(conn, user_id)
    return [UserWarehouseOut(**w) for w in items]


@router.put("/{user_id}/warehouses", response_model=list[UserWarehouseOut])
def set_user_warehouses(
    user_id: int,
    payload: UserWarehouseSet,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(USER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> list[UserWarehouseOut]:
    items = user_service.set_user_warehouses(
        conn,
        actor=actor,
        user_id=user_id,
        warehouse_ids=payload.warehouse_ids,
        ip_address=get_client_ip(request),
    )
    return [UserWarehouseOut(**w) for w in items]

