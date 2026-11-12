"""Schema untuk endpoint Dashboard operasional (DSH-F01, AC-38)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import DecimalStr


class DashboardStockSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_active_items: int
    total_qty_on_hand: DecimalStr
    total_qty_in_transit: DecimalStr
    low_stock_items_count: int


class DashboardPendingActions(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pending_po_receipt_count: int
    draft_gr_count: int
    pending_transfer_ship_count: int
    pending_transfer_receive_count: int
    active_opname_count: int


class DashboardRecentActivity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    movement_type: str
    reference_type: str
    reference_id: int
    reference_number: str | None = None
    warehouse_id: int | None = None
    warehouse_code: str | None = None
    warehouse_name: str | None = None
    item_id: int
    item_sku: str
    item_name: str
    qty_change: DecimalStr
    qty_after: DecimalStr | None = None
    actor_name: str | None = None


class DashboardAssignedWarehouse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class DashboardSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_summary: DashboardStockSummary
    pending_actions: DashboardPendingActions
    recent_activities: list[DashboardRecentActivity]
    assigned_warehouses: list[DashboardAssignedWarehouse]
