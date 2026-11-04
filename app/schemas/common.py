"""Schema umum: ErrorResponse, HealthResponse, Page[T], dan tipe Decimal string (PRD 7.4, Lampiran B)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer

T = TypeVar("T")


def _empty_str_to_none(v: Any) -> Any:
    """Mengubah query parameter string kosong ('') menjadi None agar filter opsional dari UI tidak gagal parsing."""
    if isinstance(v, str) and not v.strip():
        return None
    return v


DecimalStr = Annotated[
    Decimal,
    PlainSerializer(lambda v: f"{v:.4f}", return_type=str, when_used="json"),
]

_OptNone = Annotated[None, BeforeValidator(_empty_str_to_none)]

OptStrQuery = (
    Annotated[str, BeforeValidator(_empty_str_to_none), Field(max_length=100)]
    | _OptNone
)
OptIntQuery = Annotated[int, BeforeValidator(_empty_str_to_none)] | _OptNone
OptBoolQuery = Annotated[bool, BeforeValidator(_empty_str_to_none)] | _OptNone
OptDateQuery = Annotated[date, BeforeValidator(_empty_str_to_none)] | _OptNone
OptDatetimeQuery = (
    Annotated[datetime, BeforeValidator(_empty_str_to_none)] | _OptNone
)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

