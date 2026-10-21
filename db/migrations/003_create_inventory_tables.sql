-- ============================================================================
-- 003_create_inventory_tables.sql
-- Rujukan PRD: FR-03, FR-08, 5.3, 6.1, 6.4, 6.5, 7.4, 7.5, Lampiran A
-- Tabel: inventory_balances, stock_movements
-- ============================================================================

CREATE TABLE inventory_balances (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty_on_hand NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_inventory_balances PRIMARY KEY (id),
    CONSTRAINT uq_inventory_balances_wh_loc_item
        UNIQUE (warehouse_id, location_id, item_id),
    CONSTRAINT fk_inventory_balances_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_inventory_balances_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_inventory_balances_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_inventory_balances_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
    -- Catatan PRD 6.1: TIDAK dipasang CHECK (qty_on_hand >= 0) karena aturan
    -- allow_negative_stock berlaku per gudang dan ditegakkan di lapisan aplikasi
    -- di dalam transaksi setelah baris saldo dikunci (SELECT ... FOR UPDATE).
);

CREATE INDEX ix_inventory_balances_item_id ON inventory_balances (item_id);
CREATE INDEX ix_inventory_balances_warehouse_item ON inventory_balances (warehouse_id, item_id);

CREATE TABLE stock_movements (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    movement_type VARCHAR(30) NOT NULL,
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty_before NUMERIC(18, 4) NOT NULL,
    qty_change NUMERIC(18, 4) NOT NULL,
    qty_after NUMERIC(18, 4) NOT NULL,
    reference_type VARCHAR(30) NOT NULL,
    reference_id BIGINT NOT NULL,
    notes TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_movements PRIMARY KEY (id),
    CONSTRAINT fk_stock_movements_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movements_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movements_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movements_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_movements_movement_type CHECK (
        movement_type IN (
            'IN_PURCHASE',
            'OUT_TRANSFER',
            'IN_TRANSFER',
            'ADJUSTMENT_PLUS',
            'ADJUSTMENT_MINUS'
        )
    ),
    CONSTRAINT ck_stock_movements_reference_type CHECK (
        reference_type IN (
            'GOODS_RECEIPT',
            'STOCK_TRANSFER',
            'STOCK_OPNAME'
        )
    ),
    CONSTRAINT ck_stock_movements_qty_change_non_zero
        CHECK (qty_change <> 0),
    CONSTRAINT ck_stock_movements_balance_math
        CHECK (qty_after = qty_before + qty_change),
    CONSTRAINT ck_stock_movements_direction_sign CHECK (
        (movement_type IN ('IN_PURCHASE', 'IN_TRANSFER', 'ADJUSTMENT_PLUS') AND qty_change > 0)
        OR
        (movement_type IN ('OUT_TRANSFER', 'ADJUSTMENT_MINUS') AND qty_change < 0)
    ),
    CONSTRAINT ck_stock_movements_type_ref_match CHECK (
        (movement_type = 'IN_PURCHASE' AND reference_type = 'GOODS_RECEIPT')
        OR
        (movement_type IN ('OUT_TRANSFER', 'IN_TRANSFER') AND reference_type = 'STOCK_TRANSFER')
        OR
        (movement_type IN ('ADJUSTMENT_PLUS', 'ADJUSTMENT_MINUS') AND reference_type = 'STOCK_OPNAME')
    )
);

CREATE INDEX ix_stock_movements_wh_item_created
    ON stock_movements (warehouse_id, item_id, created_at DESC);
CREATE INDEX ix_stock_movements_wh_loc_item_id
    ON stock_movements (warehouse_id, location_id, item_id, id DESC);
CREATE INDEX ix_stock_movements_reference
    ON stock_movements (reference_type, reference_id);
CREATE INDEX ix_stock_movements_created_at
    ON stock_movements (created_at DESC);

