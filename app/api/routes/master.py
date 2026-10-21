"""Routes Manajemen Master Data: Kategori, UoM, Pemasok, dan Barang (FR-02, Matriks 3.1 PRD)."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from psycopg import Connection

from app.api.deps import get_client_ip
from app.core.database import get_conn
from app.core.permissions import MASTER_MANAGE, MASTER_READ, require_permission
from app.schemas.common import Page
from app.schemas.master import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ItemCreate,
    ItemOut,
    ItemUpdate,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
    UomCreate,
    UomOut,
    UomUpdate,
)
from app.services import master_service

router = APIRouter(tags=["Master Data"])


# ============================================================================
# Categories (/api/v1/categories)
# ============================================================================
@router.get("/categories", response_model=Page[CategoryOut])
def list_categories(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[CategoryOut]:
    page = master_service.list_categories(
        conn,
        limit=limit,
        offset=offset,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[CategoryOut](**page)


@router.post(
    "/categories",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: CategoryCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(MASTER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> CategoryOut:
    created = master_service.create_category(
        conn,
        actor=actor,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return CategoryOut(**created)


@router.get("/categories/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: int,
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> CategoryOut:
    cat = master_service.get_category(conn, category_id)
    return CategoryOut(**cat)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(MASTER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> CategoryOut:
    updated = master_service.update_category(
        conn,
        actor=actor,
        category_id=category_id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return CategoryOut(**updated)


# ============================================================================
# Units of Measure (/api/v1/uoms)
# ============================================================================
@router.get("/uoms", response_model=Page[UomOut])
def list_uoms(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[UomOut]:
    page = master_service.list_uoms(
        conn,
        limit=limit,
        offset=offset,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[UomOut](**page)


@router.post(
    "/uoms",
    response_model=UomOut,
    status_code=status.HTTP_201_CREATED,
)
def create_uom(
    payload: UomCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(MASTER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> UomOut:
    created = master_service.create_uom(
        conn,
        actor=actor,
        code=payload.code,
        name=payload.name,
        allow_decimal=payload.allow_decimal,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return UomOut(**created)


@router.get("/uoms/{uom_id}", response_model=UomOut)
def get_uom(
    uom_id: int,
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> UomOut:
    uom = master_service.get_uom(conn, uom_id)
    return UomOut(**uom)


@router.patch("/uoms/{uom_id}", response_model=UomOut)
def update_uom(
    uom_id: int,
    payload: UomUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(MASTER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> UomOut:
    updated = master_service.update_uom(
        conn,
        actor=actor,
        uom_id=uom_id,
        code=payload.code,
        name=payload.name,
        allow_decimal=payload.allow_decimal,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return UomOut(**updated)


# ============================================================================
# Suppliers (/api/v1/suppliers)
# ============================================================================
@router.get("/suppliers", response_model=Page[SupplierOut])
def list_suppliers(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[SupplierOut]:
    page = master_service.list_suppliers(
        conn,
        limit=limit,
        offset=offset,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[SupplierOut](**page)


@router.post(
    "/suppliers",
    response_model=SupplierOut,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier(
    payload: SupplierCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(MASTER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> SupplierOut:
    created = master_service.create_supplier(
        conn,
        actor=actor,
        code=payload.code,
        name=payload.name,
        contact_person=payload.contact_person,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return SupplierOut(**created)


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
def get_supplier(
    supplier_id: int,
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> SupplierOut:
    supplier = master_service.get_supplier(conn, supplier_id)
    return SupplierOut(**supplier)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(MASTER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> SupplierOut:
    updated = master_service.update_supplier(
        conn,
        actor=actor,
        supplier_id=supplier_id,
        code=payload.code,
        name=payload.name,
        contact_person=payload.contact_person,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return SupplierOut(**updated)


# ============================================================================
# Items (/api/v1/items)
# ============================================================================
@router.get("/items", response_model=Page[ItemOut])
def list_items(
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    category_id: int | None = Query(default=None),
    uom_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str | None = Query(default=None),
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> Page[ItemOut]:
    page = master_service.list_items(
        conn,
        limit=limit,
        offset=offset,
        category_id=category_id,
        uom_id=uom_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return Page[ItemOut](**page)


@router.post(
    "/items",
    response_model=ItemOut,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    payload: ItemCreate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(MASTER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> ItemOut:
    created = master_service.create_item(
        conn,
        actor=actor,
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        category_id=payload.category_id,
        uom_id=payload.uom_id,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return ItemOut(**created)


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(
    item_id: int,
    _actor: dict[str, Any] = Depends(require_permission(MASTER_READ)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> ItemOut:
    item = master_service.get_item(conn, item_id)
    return ItemOut(**item)


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    payload: ItemUpdate,
    request: Request,
    actor: dict[str, Any] = Depends(require_permission(MASTER_MANAGE)),
    conn: Connection[dict[str, Any]] = Depends(get_conn),
) -> ItemOut:
    updated = master_service.update_item(
        conn,
        actor=actor,
        item_id=item_id,
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        category_id=payload.category_id,
        uom_id=payload.uom_id,
        is_active=payload.is_active,
        ip_address=get_client_ip(request),
    )
    return ItemOut(**updated)

