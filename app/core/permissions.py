"""Konstanta kode permission (Matriks 3.1 PRD) dan dependency require_permission."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends

from app.api.deps import get_current_user
from app.core.exceptions import PermissionDenied

# Daftar kode permission sesuai Matriks 3.1 PRD + Tahap 34 & 38
USER_MANAGE = "user:manage"
WAREHOUSE_MANAGE = "warehouse:manage"
LOCATION_MANAGE = "location:manage"
MASTER_MANAGE = "master:manage"
MASTER_READ = "master:read"
PO_CREATE = "po:create"
PO_ISSUE = "po:issue"
PO_APPROVE_L1 = "po:approve_l1"
PO_APPROVE_L2 = "po:approve_l2"
PO_CANCEL = "po:cancel"
PO_CLOSE = "po:close"
PO_READ = "po:read"
GR_CREATE = "gr:create"
GR_POST = "gr:post"
GR_READ = "gr:read"
TRANSFER_CREATE = "transfer:create"
TRANSFER_APPROVE = "transfer:approve"
TRANSFER_SHIP = "transfer:ship"
TRANSFER_RECEIVE = "transfer:receive"
TRANSFER_READ = "transfer:read"
OPNAME_MANAGE = "opname:manage"
OPNAME_COUNT = "opname:count"
OPNAME_APPROVE_L1 = "opname:approve_l1"
OPNAME_APPROVE_L2 = "opname:approve_l2"
OPNAME_READ = "opname:read"
STOCK_READ = "stock:read"
LEDGER_READ = "ledger:read"
AUDIT_READ = "audit:read"
SETTINGS_MANAGE = "settings:manage"

ALL_PERMISSIONS: tuple[str, ...] = (
    USER_MANAGE,
    WAREHOUSE_MANAGE,
    LOCATION_MANAGE,
    MASTER_MANAGE,
    MASTER_READ,
    PO_CREATE,
    PO_ISSUE,
    PO_APPROVE_L1,
    PO_APPROVE_L2,
    PO_CANCEL,
    PO_CLOSE,
    PO_READ,
    GR_CREATE,
    GR_POST,
    GR_READ,
    TRANSFER_CREATE,
    TRANSFER_APPROVE,
    TRANSFER_SHIP,
    TRANSFER_RECEIVE,
    TRANSFER_READ,
    OPNAME_MANAGE,
    OPNAME_COUNT,
    OPNAME_APPROVE_L1,
    OPNAME_APPROVE_L2,
    OPNAME_READ,
    STOCK_READ,
    LEDGER_READ,
    AUDIT_READ,
    SETTINGS_MANAGE,
)

ROLE_SUPER_ADMIN = "Super Admin"
ROLE_WAREHOUSE_MANAGER = "Warehouse Manager"
ROLE_WAREHOUSE_SUPERVISOR = "Warehouse Supervisor"
ROLE_PROCUREMENT_MANAGER = "Procurement Manager"
ROLE_PURCHASING_STAFF = "Purchasing Staff"
ROLE_WAREHOUSE_STAFF = "Warehouse Staff"
ROLE_AUDITOR = "Auditor"

# Peran yang memiliki akses baca lintas semua gudang (PRD 3.2 poin 2).
UNSCOPED_READ_ROLES: frozenset[str] = frozenset({ROLE_SUPER_ADMIN, ROLE_AUDITOR})


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


def require_any_permission(*permission_codes: str) -> Callable[..., dict[str, Any]]:
    """Dependency level route untuk memastikan pengguna memiliki minimal satu dari daftar permission."""

    def _checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        permissions: set[str] = set(current_user.get("permissions", []))
        if not any(code in permissions for code in permission_codes):
            raise PermissionDenied(
                f"Anda tidak memiliki salah satu izin yang dibutuhkan ({', '.join(permission_codes)}) untuk melakukan aksi ini.",
                details={"required_any_permissions": list(permission_codes)},
            )
        return current_user

    return _checker


def check_sod_actor(
    actor: dict[str, Any],
    forbidden_actor_ids: set[int] | list[int] | tuple[int | None, ...],
    *,
    action_label: str = "menyetujui dokumen ini",
) -> bool:
    """Memeriksa Segregation of Duties (maker-checker).

    Mengembalikan True apabila terjadi override oleh Super Admin (untuk dicatat ke audit log).
    Melempar PermissionDenied (SOD_VIOLATION) bagi role lain apabila actor termasuk pembuat/penginput.
    """
    normalized_ids = {int(uid) for uid in forbidden_actor_ids if uid is not None}
    actor_id = int(actor["id"])
    if actor_id not in normalized_ids:
        return False

    if actor.get("role_name") == ROLE_SUPER_ADMIN:
        return True

    raise PermissionDenied(
        f"Pelanggaran Segregation of Duties: pembuat atau penginput dokumen tidak diperbolehkan {action_label}.",
        details={
            "code": "SOD_VIOLATION",
            "actor_id": actor_id,
            "forbidden_actor_ids": sorted(normalized_ids),
        },
    )

