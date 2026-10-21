"""Konstanta kode permission (Matriks 3.1 PRD) dan dependency require_permission."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends

from app.api.deps import get_current_user
from app.core.exceptions import PermissionDenied

# Daftar 24 kode permission sesuai Matriks 3.1 PRD
USER_MANAGE = "user:manage"
WAREHOUSE_MANAGE = "warehouse:manage"
LOCATION_MANAGE = "location:manage"
MASTER_MANAGE = "master:manage"
MASTER_READ = "master:read"
PO_CREATE = "po:create"
PO_ISSUE = "po:issue"
PO_CANCEL = "po:cancel"
PO_CLOSE = "po:close"
PO_READ = "po:read"
GR_MANAGE = "gr:manage"
GR_READ = "gr:read"
TRANSFER_CREATE = "transfer:create"
TRANSFER_APPROVE = "transfer:approve"
TRANSFER_SHIP = "transfer:ship"
TRANSFER_RECEIVE = "transfer:receive"
TRANSFER_READ = "transfer:read"
OPNAME_MANAGE = "opname:manage"
OPNAME_COUNT = "opname:count"
OPNAME_APPROVE = "opname:approve"
OPNAME_READ = "opname:read"
STOCK_READ = "stock:read"
LEDGER_READ = "ledger:read"
AUDIT_READ = "audit:read"

ALL_PERMISSIONS: tuple[str, ...] = (
    USER_MANAGE,
    WAREHOUSE_MANAGE,
    LOCATION_MANAGE,
    MASTER_MANAGE,
    MASTER_READ,
    PO_CREATE,
    PO_ISSUE,
    PO_CANCEL,
    PO_CLOSE,
    PO_READ,
    GR_MANAGE,
    GR_READ,
    TRANSFER_CREATE,
    TRANSFER_APPROVE,
    TRANSFER_SHIP,
    TRANSFER_RECEIVE,
    TRANSFER_READ,
    OPNAME_MANAGE,
    OPNAME_COUNT,
    OPNAME_APPROVE,
    OPNAME_READ,
    STOCK_READ,
    LEDGER_READ,
    AUDIT_READ,
)

ROLE_SUPER_ADMIN = "Super Admin"
ROLE_WAREHOUSE_MANAGER = "Warehouse Manager"
ROLE_PURCHASING_STAFF = "Purchasing Staff"
ROLE_WAREHOUSE_STAFF = "Warehouse Staff"
ROLE_AUDITOR = "Auditor"


def require_permission(permission_code: str) -> Callable[..., dict[str, Any]]:
    """Dependency level route untuk memastikan pengguna aktif memiliki kode permission tertentu."""

    def _checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        permissions: set[str] = set(current_user.get("permissions", []))
        if permission_code not in permissions:
            raise PermissionDenied(
                f"Anda tidak memiliki izin '{permission_code}' untuk melakukan aksi ini.",
                details={"required_permission": permission_code},
            )
        return current_user

    return _checker

