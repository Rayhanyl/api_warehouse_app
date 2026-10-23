"""Service inti mutasi persediaan — SATU-SATUNYA pintu pengubah saldo stok & penulis buku besar (FR-03, FR-08, PRD 6.1, 6.5, 6.6)."""

from decimal import Decimal
from typing import Any

from psycopg import Connection
from psycopg.pq import TransactionStatus

from app.core.exceptions import (
    InactiveReferenceError,
    InsufficientStock,
    InvalidLocationError,
    LocationFrozen,
    NotFoundError,
    ValidationDomainError,
)
from app.repositories import inventory_repo, opname_repo
from app.utils.enums import (
    ADJUSTMENT_MOVEMENT_TYPES,
    MOVEMENT_REFERENCE_MAP,
    NEGATIVE_MOVEMENT_TYPES,
    POSITIVE_MOVEMENT_TYPES,
    MovementType,
    ReferenceType,
)

FOUR_PLACES = Decimal("0.0001")


def _normalize_decimal_qty(value: Decimal) -> Decimal:
    """Memastikan kuantitas bertipe Decimal (bukan float) dengan maksimum 4 angka di belakang koma (Invarian 10, PRD 6.9)."""
    if isinstance(value, float):
        raise ValidationDomainError(
            "Kuantitas harus bertipe Decimal, tidak boleh float.",
            details={"value": str(value)},
        )
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except Exception as exc:
            raise ValidationDomainError(
                "Format kuantitas desimal tidak valid.",
                details={"value": str(value)},
            ) from exc

    quantized = value.quantize(FOUR_PLACES)
    if quantized != value:
        raise ValidationDomainError(
            "Kuantitas maksimal memiliki 4 angka di belakang koma.",
            details={"value": str(value)},
        )
    return quantized


def apply_movement(
    conn: Connection[dict[str, Any]],
    *,
    movement_type: str | MovementType,
    warehouse_id: int,
    location_id: int,
    item_id: int,
    qty_change: Decimal,
    reference_type: str | ReferenceType,
    reference_id: int,
    created_by: int,
    notes: str | None = None,
) -> dict[str, Any]:
    """Menerapkan satu pergerakan stok ke inventory_balances dan mencatatnya ke stock_movements.

    Wajib dipanggil di dalam blok transaksi (`with conn.transaction():`) milik use case pemanggil.
    Urutan langkah sesuai FOLDER_STRUCTURE.md 4.1 & PRD 6.5:
      1. Kunci lokasi (`FOR SHARE`), validasi kepemilikan gudang & pemeriksaan pembekuan Opname (kecuali `ADJUSTMENT_*`).
      2. Validasi barang & aturan UoM (`allow_decimal`).
      3. Pastikan baris saldo ada (`INSERT ... ON CONFLICT DO NOTHING`).
      4. Kunci baris saldo (`SELECT ... FOR UPDATE`) -> ambil `qty_before`.
      5. Validasi stok negatif bila `qty_change < 0` dan `allow_negative_stock = FALSE`.
      6. Update `inventory_balances.qty_on_hand = qty_after`.
      7. Insert baris baru ke `stock_movements`.
    """
    if conn.info.transaction_status == TransactionStatus.IDLE:
        raise RuntimeError(
            "inventory_service.apply_movement wajib dipanggil di dalam blok transaksi aktif (`with conn.transaction():`)."
        )

    mov_type = (
        movement_type.value
        if isinstance(movement_type, MovementType)
        else str(movement_type).strip().upper()
    )
    ref_type = (
        reference_type.value
        if isinstance(reference_type, ReferenceType)
        else str(reference_type).strip().upper()
    )

    if mov_type not in MOVEMENT_REFERENCE_MAP:
        raise ValidationDomainError(
            f"Jenis pergerakan stok '{mov_type}' tidak valid.",
            details={"movement_type": mov_type},
        )
    expected_ref = MOVEMENT_REFERENCE_MAP[mov_type]
    if ref_type != expected_ref:
        raise ValidationDomainError(
            f"Jenis pergerakan '{mov_type}' wajib menggunakan reference_type '{expected_ref}'.",
            details={
                "movement_type": mov_type,
                "reference_type": ref_type,
                "expected_reference_type": expected_ref,
            },
        )

    norm_change = _normalize_decimal_qty(qty_change)
    if norm_change == Decimal("0.0000"):
        raise ValidationDomainError(
            "Perubahan kuantitas (qty_change) tidak boleh bernilai 0.",
            details={"qty_change": str(norm_change)},
        )
    if mov_type in POSITIVE_MOVEMENT_TYPES and norm_change <= Decimal("0.0000"):
        raise ValidationDomainError(
            f"Jenis pergerakan '{mov_type}' harus memiliki qty_change positif (> 0).",
            details={"movement_type": mov_type, "qty_change": str(norm_change)},
        )
    if mov_type in NEGATIVE_MOVEMENT_TYPES and norm_change >= Decimal("0.0000"):
        raise ValidationDomainError(
            f"Jenis pergerakan '{mov_type}' harus memiliki qty_change negatif (< 0).",
            details={"movement_type": mov_type, "qty_change": str(norm_change)},
        )

    # 1. Kunci lokasi (FOR SHARE) & periksa validitas + pembekuan Opname
    loc = inventory_repo.lock_location_for_share(conn, location_id)
    if not loc or int(loc["warehouse_id"]) != int(warehouse_id):
        raise InvalidLocationError(
            "Lokasi penyimpanan tidak ditemukan atau bukan milik gudang yang dipilih.",
            details={"warehouse_id": warehouse_id, "location_id": location_id},
        )

    is_adjustment = mov_type in ADJUSTMENT_MOVEMENT_TYPES
    if not is_adjustment:
        if not loc["is_active"]:
            raise InvalidLocationError(
                "Lokasi penyimpanan sedang tidak aktif.",
                details={"warehouse_id": warehouse_id, "location_id": location_id},
            )
        if not loc["warehouse_is_active"]:
            raise InactiveReferenceError(
                "Gudang sedang tidak aktif.",
                details={"warehouse_id": warehouse_id},
            )

        freezing_opname = opname_repo.get_active_opname_freezing_location(
            conn, warehouse_id=warehouse_id, location_id=location_id
        )
        if freezing_opname is not None:
            raise LocationFrozen(
                f"Lokasi '{loc['code']}' sedang dibekukan oleh sesi Stock Opname '{freezing_opname['opname_number']}'.",
                details={
                    "warehouse_id": warehouse_id,
                    "location_id": location_id,
                    "location_code": loc["code"],
                    "opname_id": freezing_opname["id"],
                    "opname_number": freezing_opname["opname_number"],
                },
            )

    # 2. Periksa barang & aturan UoM allow_decimal
    item = inventory_repo.get_item_with_uom(conn, item_id)
    if not item:
        raise NotFoundError(
            "Barang tidak ditemukan.",
            details={"item_id": item_id},
        )
    if not is_adjustment and not item["is_active"]:
        raise InactiveReferenceError(
            f"Barang '{item['sku']}' berstatus tidak aktif.",
            details={"item_id": item_id, "sku": item["sku"]},
        )
    if not bool(item["allow_decimal"]) and norm_change != norm_change.to_integral_value():
        raise ValidationDomainError(
            f"Barang '{item['sku']}' menggunakan UoM '{item['uom_code']}' yang tidak mengizinkan kuantitas desimal.",
            details={
                "item_id": item_id,
                "sku": item["sku"],
                "uom_code": item["uom_code"],
                "qty_change": str(norm_change),
            },
        )

    # 3. Pastikan baris saldo ada (INSERT ... ON CONFLICT DO NOTHING)
    inventory_repo.ensure_balance_row(
        conn,
        warehouse_id=warehouse_id,
        location_id=location_id,
        item_id=item_id,
        actor_id=created_by,
    )

    # 4. Kunci baris saldo (SELECT ... FOR UPDATE)
    balance_row = inventory_repo.lock_balance_row(
        conn,
        warehouse_id=warehouse_id,
        location_id=location_id,
        item_id=item_id,
    )
    qty_before = Decimal(balance_row["qty_on_hand"]).quantize(FOUR_PLACES)
    qty_after = (qty_before + norm_change).quantize(FOUR_PLACES)

    # 5. Validasi stok negatif (PRD 6.1 & Invarian 5)
    if norm_change < Decimal("0.0000") and qty_after < Decimal("0.0000"):
        if not bool(loc["allow_negative_stock"]):
            raise InsufficientStock(
                f"Stok barang '{item['sku']}' pada lokasi '{loc['code']}' tidak mencukupi.",
                details={
                    "warehouse_id": warehouse_id,
                    "location_id": location_id,
                    "location_code": loc["code"],
                    "item_id": item_id,
                    "item_sku": item["sku"],
                    "qty_available": f"{qty_before:.4f}",
                    "qty_requested": f"{abs(norm_change):.4f}",
                },
            )

    # 6. Update saldo stok
    inventory_repo.update_balance_qty(
        conn,
        balance_id=int(balance_row["id"]),
        qty_after=qty_after,
    )

    # 7. Tulis baris ke buku besar stock_movements
    movement = inventory_repo.insert_stock_movement(
        conn,
        movement_type=mov_type,
        warehouse_id=warehouse_id,
        location_id=location_id,
        item_id=item_id,
        qty_before=qty_before,
        qty_change=norm_change,
        qty_after=qty_after,
        reference_type=ref_type,
        reference_id=reference_id,
        notes=notes,
        created_by=created_by,
    )
    return movement

