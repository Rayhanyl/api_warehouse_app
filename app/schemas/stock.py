"""Schema Pydantic untuk tampilan saldo stok (per lokasi, per gudang, agregat) & buku besar (FR-03, FR-08, PRD 7.4)."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import DecimalStr


class StockLocationBalanceOut(BaseModel):
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    location_id: int
    location_code: str
    location_name: str
    item_id: int
    item_sku: str
    item_name: str
    category_id: int
    category_name: str
    uom_id: int
    uom_code: str
    qty_on_hand: DecimalStr
    qty_in_transit: DecimalStr
    updated_at: datetime | None = None


class StockWarehouseBalanceOut(BaseModel):
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    item_id: int
    item_sku: str
    item_name: str
    category_id: int
    category_name: str
    uom_id: int
    uom_code: str
    qty_on_hand: DecimalStr
    qty_in_transit: DecimalStr


class StockSummaryOut(BaseModel):
    item_id: int
    item_sku: str
    item_name: str
    category_id: int
    category_name: str
    uom_id: int
    uom_code: str
    qty_on_hand: DecimalStr
    qty_in_transit: DecimalStr


class StockMovementOut(BaseModel):
    id: int
    movement_type: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    location_id: int
    location_code: str
    location_name: str
    item_id: int
    item_sku: str
    item_name: str
    uom_code: str
    qty_before: DecimalStr
    qty_change: DecimalStr
    qty_after: DecimalStr
    reference_type: str
    reference_id: int
    notes: str | None = None
    created_by: int
    created_by_username: str
    created_at: datetime

