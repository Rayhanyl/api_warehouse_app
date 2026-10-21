"""Definisi DomainError dan seluruh kode error sesuai Lampiran B PRD."""

from typing import Any


class DomainError(Exception):
    """Base exception untuk seluruh aturan bisnis WMS API."""

    code: str = "DOMAIN_ERROR"
    http_status: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details: dict[str, Any] = details or {}


class AuthInvalidCredentials(DomainError):
    code = "AUTH_INVALID_CREDENTIALS"
    http_status = 401


class AuthTokenInvalid(DomainError):
    code = "AUTH_TOKEN_INVALID"
    http_status = 401


class AuthTooManyAttempts(DomainError):
    code = "AUTH_TOO_MANY_ATTEMPTS"
    http_status = 429


class PermissionDenied(DomainError):
    code = "PERMISSION_DENIED"
    http_status = 403


class WarehouseNotAssigned(DomainError):
    code = "WAREHOUSE_NOT_ASSIGNED"
    http_status = 403


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class ValidationDomainError(DomainError):
    code = "VALIDATION_ERROR"
    http_status = 422


class InvalidLocationError(DomainError):
    code = "INVALID_LOCATION"
    http_status = 422


class InactiveReferenceError(DomainError):
    code = "INACTIVE_REFERENCE"
    http_status = 422


class DuplicateError(DomainError):
    code = "DUPLICATE"
    http_status = 409


class InvalidStateTransition(DomainError):
    code = "INVALID_STATE_TRANSITION"
    http_status = 409


class InsufficientStock(DomainError):
    code = "INSUFFICIENT_STOCK"
    http_status = 409


class OverReceipt(DomainError):
    code = "OVER_RECEIPT"
    http_status = 409


class TransferQtyExceedsShipped(DomainError):
    code = "TRANSFER_QTY_EXCEEDS_SHIPPED"
    http_status = 409


class LocationFrozen(DomainError):
    code = "LOCATION_FROZEN"
    http_status = 409


class EntityInUse(DomainError):
    code = "ENTITY_IN_USE"
    http_status = 409

