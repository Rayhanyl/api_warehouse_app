-- ============================================================================
-- 005_create_transfer_opname.sql
-- Rujukan PRD: FR-06, FR-07, 5.1, 6.3, 6.6, 6.7, 6.9, 7.5, Lampiran A
-- Tabel: stock_transfers, stock_transfer_lines, stock_opnames, stock_opname_lines
-- ============================================================================

CREATE TABLE stock_transfers (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    transfer_number VARCHAR(50) NOT NULL,
    source_warehouse_id BIGINT NOT NULL,
    source_location_id BIGINT NOT NULL,
    destination_warehouse_id BIGINT NOT NULL,
    destination_location_id BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    notes TEXT,
    approved_by BIGINT,
    approved_at TIMESTAMPTZ,
    shipped_by BIGINT,
    shipped_at TIMESTAMPTZ,
    received_by BIGINT,
    received_at TIMESTAMPTZ,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_transfers PRIMARY KEY (id),
    CONSTRAINT uq_stock_transfers_transfer_number UNIQUE (transfer_number),
    CONSTRAINT fk_stock_transfers_source_warehouse_id
        FOREIGN KEY (source_warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_source_location_warehouse
        FOREIGN KEY (source_location_id, source_warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_destination_warehouse_id
        FOREIGN KEY (destination_warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_destination_location_warehouse
        FOREIGN KEY (destination_location_id, destination_warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_approved_by
        FOREIGN KEY (approved_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_shipped_by
        FOREIGN KEY (shipped_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_received_by
        FOREIGN KEY (received_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_transfers_status CHECK (
        status IN ('DRAFT', 'APPROVED', 'SHIPPED', 'RECEIVED', 'CANCELLED')
    ),
    -- PRD 6.3: Kombinasi (source_warehouse_id, source_location_id) tidak boleh sama dengan (destination_warehouse_id, destination_location_id)
    CONSTRAINT ck_stock_transfers_different_src_dst CHECK (
        source_warehouse_id <> destination_warehouse_id
        OR source_location_id <> destination_location_id
    )
);

CREATE INDEX ix_stock_transfers_source_wh ON stock_transfers (source_warehouse_id);
CREATE INDEX ix_stock_transfers_dest_wh ON stock_transfers (destination_warehouse_id);
CREATE INDEX ix_stock_transfers_status ON stock_transfers (status);

CREATE TABLE stock_transfer_lines (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    transfer_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty NUMERIC(18, 4) NOT NULL,
    qty_received NUMERIC(18, 4),
    variance_reason TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_transfer_lines PRIMARY KEY (id),
    CONSTRAINT uq_stock_transfer_lines_transfer_item
        UNIQUE (transfer_id, item_id),
    CONSTRAINT fk_stock_transfer_lines_transfer_id
        FOREIGN KEY (transfer_id) REFERENCES stock_transfers (id) ON DELETE CASCADE,
    CONSTRAINT fk_stock_transfer_lines_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfer_lines_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_transfer_lines_qty_positive
        CHECK (qty > 0),
    CONSTRAINT ck_stock_transfer_lines_qty_received_bounds
        CHECK (qty_received IS NULL OR (0 <= qty_received AND qty_received <= qty)),
    -- PRD 6.7: Bila qty_received < qty, alasan selisih (variance_reason) wajib diisi
    CONSTRAINT ck_stock_transfer_lines_variance_reason CHECK (
        qty_received IS NULL
        OR qty_received = qty
        OR (variance_reason IS NOT NULL AND length(btrim(variance_reason)) > 0)
    )
);

CREATE INDEX ix_stock_transfer_lines_transfer_id ON stock_transfer_lines (transfer_id);
CREATE INDEX ix_stock_transfer_lines_item_id ON stock_transfer_lines (item_id);

CREATE TABLE stock_opnames (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    opname_number VARCHAR(50) NOT NULL,
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    notes TEXT,
    started_at TIMESTAMPTZ,
    started_by BIGINT,
    submitted_at TIMESTAMPTZ,
    submitted_by BIGINT,
    approved_by BIGINT,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_opnames PRIMARY KEY (id),
    CONSTRAINT uq_stock_opnames_opname_number UNIQUE (opname_number),
    CONSTRAINT uq_stock_opnames_id_warehouse UNIQUE (id, warehouse_id),
    CONSTRAINT fk_stock_opnames_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    -- MATCH SIMPLE (bawaan PostgreSQL): bila location_id NULL (cakupan seluruh gudang),
    -- FK dilewati; bila location_id diisi, wajib milik warehouse_id tersebut.
    CONSTRAINT fk_stock_opnames_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opnames_started_by
        FOREIGN KEY (started_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opnames_submitted_by
        FOREIGN KEY (submitted_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opnames_approved_by
        FOREIGN KEY (approved_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opnames_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_opnames_status CHECK (
        status IN (
            'DRAFT',
            'IN_PROGRESS',
            'WAITING_APPROVAL',
            'COMPLETED',
            'CANCELLED'
        )
    )
);

CREATE INDEX ix_stock_opnames_warehouse_id ON stock_opnames (warehouse_id);
CREATE INDEX ix_stock_opnames_location_id ON stock_opnames (location_id);
CREATE INDEX ix_stock_opnames_status ON stock_opnames (status);

-- Indeks parsial untuk mempercepat pemeriksaan pembekuan lokasi (PRD 6.6 & FR-07)
CREATE INDEX ix_stock_opnames_active_scope
    ON stock_opnames (warehouse_id, location_id)
    WHERE status IN ('IN_PROGRESS', 'WAITING_APPROVAL');

CREATE TABLE stock_opname_lines (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    opname_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty_system NUMERIC(18, 4) NOT NULL,
    qty_physical NUMERIC(18, 4),
    qty_variance NUMERIC(18, 4) GENERATED ALWAYS AS (qty_physical - qty_system) STORED,
    counted_by BIGINT,
    counted_at TIMESTAMPTZ,
    notes TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_opname_lines PRIMARY KEY (id),
    CONSTRAINT uq_stock_opname_lines_opname_loc_item
        UNIQUE (opname_id, location_id, item_id),
    CONSTRAINT fk_stock_opname_lines_header
        FOREIGN KEY (opname_id, warehouse_id)
        REFERENCES stock_opnames (id, warehouse_id) ON DELETE CASCADE,
    CONSTRAINT fk_stock_opname_lines_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opname_lines_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opname_lines_counted_by
        FOREIGN KEY (counted_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opname_lines_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_opname_lines_qty_physical_non_negative
        CHECK (qty_physical IS NULL OR qty_physical >= 0)
);

CREATE INDEX ix_stock_opname_lines_opname_id ON stock_opname_lines (opname_id);
CREATE INDEX ix_stock_opname_lines_location_id ON stock_opname_lines (location_id);

