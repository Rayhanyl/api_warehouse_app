"""Routes Manajemen Gudang (Warehouse) dan Lokasi Penyimpanan (Storage Location) (FR-02, Matriks 3.1 & 3.2 PRD)."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from psycopg import Connection

from app.api.deps import get_client_ip
from app.core.database import get_conn
from app.core.permissions import (
    LOCATION_MANAGE,
    MASTER_READ,
    WAREHOUSE_MANAGE,
    require_permission,
)
from app.schemas.common import Page
from app.schemas.warehouse import (
    StorageLocationCreate,
    StorageLocationOut,
    StorageLocationUpdate,
    WarehouseCreate,
    WarehouseLocationCreate,
    WarehouseOut,
    WarehouseUpdate,
)
from app.services import warehouse_service

router = APIRouter(tags=["Warehouses & Locations"])


# ============================================================================
# Warehouses (/api/v1/warehouses)
# ============================================================================
@router.get("/warehouses", response_model=Page[WarehouseOut])
def list_warehouses(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[WarehouseOut]:
    page = warehouse_service.list_warehouses(
        conn,
        limit=limit,
        offset=offset,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[WarehouseOut](**page)


@router.post(
    "/warehouses",
    response_model=WarehouseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_warehouse(
    payload: WarehouseCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(WAREHOUSE_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> WarehouseOut:
    created = warehouse_service.create_warehouse(
        conn,
        actor=actor,
        code=payload.code,
        name=payload.name,
        address=payload.address,
        allow_negative_stock=payload.allow_negative_stock,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return WarehouseOut(**created)


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseOut)
def get_warehouse(
    warehouse_id: int,
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> WarehouseOut:
    warehouse = warehouse_service.get_warehouse(conn, warehouse_id)
    return WarehouseOut(**warehouse)


@router.patch("/warehouses/{warehouse_id}", response_model=WarehouseOut)
def update_warehouse(
    warehouse_id: int,
    payload: WarehouseUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(WAREHOUSE_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> WarehouseOut:
    updated = warehouse_service.update_warehouse(
        conn,
        actor=actor,
        warehouse_id=warehouse_id,
        code=payload.code,
        name=payload.name,
        address=payload.address,
        allow_negative_stock=payload.allow_negative_stock,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return WarehouseOut(**updated)


# ============================================================================
# Storage Locations (/api/v1/warehouses/{warehouse_id}/locations & /api/v1/locations)
# ============================================================================
@router.get(
    "/warehouses/{warehouse_id}/locations",
    response_model=Page[StorageLocationOut],
)
def list_warehouse_locations(
    warehouse_id: int,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[StorageLocationOut]:
    page = warehouse_service.list_locations(
        conn,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        require_warehouse_exists=True,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[StorageLocationOut](**page)


@router.post(
    "/warehouses/{warehouse_id}/locations",
    response_model=StorageLocationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_warehouse_location(
    warehouse_id: int,
    payload: WarehouseLocationCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(LOCATION_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StorageLocationOut:
    created = warehouse_service.create_location(
        conn,
        actor=actor,
        warehouse_id=warehouse_id,
        code=payload.code,
        name=payload.name,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return StorageLocationOut(**created)


@router.get("/locations", response_model=Page[StorageLocationOut])
def list_locations(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    warehouse_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[StorageLocationOut]:
    page = warehouse_service.list_locations(
        conn,
        limit=limit,
        offset=offset,
        warehouse_id=warehouse_id,
        require_warehouse_exists=False,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[StorageLocationOut](**page)


@router.post(
    "/locations",
    response_model=StorageLocationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    payload: StorageLocationCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(LOCATION_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StorageLocationOut:
    created = warehouse_service.create_location(
        conn,
        actor=actor,
        warehouse_id=payload.warehouse_id,
        code=payload.code,
        name=payload.name,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return StorageLocationOut(**created)


@router.get("/locations/{location_id}", response_model=StorageLocationOut)
def get_location(
    location_id: int,
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StorageLocationOut:
    location = warehouse_service.get_location(conn, location_id)
    return StorageLocationOut(**location)


@router.patch("/locations/{location_id}", response_model=StorageLocationOut)
def update_location(
    location_id: int,
    payload: StorageLocationUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(LOCATION_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> StorageLocationOut:
    updated = warehouse_service.update_location(
        conn,
        actor=actor,
        location_id=location_id,
        code=payload.code,
        name=payload.name,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return StorageLocationOut(**updated)

