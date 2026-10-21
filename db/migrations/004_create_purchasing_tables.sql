-- ============================================================================
-- 004_create_purchasing_tables.sql
-- Rujukan PRD: FR-04, FR-05, 5.1, 6.2, 6.3, 6.9, 7.5, Lampiran A
-- Tabel: purchase_orders, po_lines, goods_receipts, gr_lines
-- ============================================================================

CREATE TABLE purchase_orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    po_number VARCHAR(50) NOT NULL,
    supplier_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    order_date DATE NOT NULL,
    notes TEXT,
    issued_at TIMESTAMPTZ,
    issued_by BIGINT,
    closed_reason TEXT,
    closed_at TIMESTAMPTZ,
    closed_by BIGINT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_purchase_orders PRIMARY KEY (id),
    CONSTRAINT uq_purchase_orders_po_number UNIQUE (po_number),
    CONSTRAINT uq_purchase_orders_id_warehouse UNIQUE (id, warehouse_id),
    CONSTRAINT fk_purchase_orders_supplier_id
        FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_issued_by
        FOREIGN KEY (issued_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_closed_by
        FOREIGN KEY (closed_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_purchase_orders_status CHECK (
        status IN (
            'DRAFT',
            'ISSUED',
            'PARTIALLY_RECEIVED',
            'RECEIVED',
            'CLOSED',
            'CANCELLED'
        )
    ),
    CONSTRAINT ck_purchase_orders_closed_reason CHECK (
        status <> 'CLOSED' OR (closed_reason IS NOT NULL AND length(btrim(closed_reason)) > 0)
    )
);

CREATE INDEX ix_purchase_orders_supplier_id ON purchase_orders (supplier_id);
CREATE INDEX ix_purchase_orders_warehouse_id ON purchase_orders (warehouse_id);
CREATE INDEX ix_purchase_orders_status ON purchase_orders (status);
CREATE INDEX ix_purchase_orders_order_date ON purchase_orders (order_date DESC);

CREATE TABLE po_lines (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    po_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty_ordered NUMERIC(18, 4) NOT NULL,
    qty_received NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    notes TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_po_lines PRIMARY KEY (id),
    CONSTRAINT uq_po_lines_po_item UNIQUE (po_id, item_id),
    CONSTRAINT uq_po_lines_id_po UNIQUE (id, po_id),
    CONSTRAINT fk_po_lines_po_id
        FOREIGN KEY (po_id) REFERENCES purchase_orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_po_lines_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_po_lines_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_po_lines_qty_ordered_positive
        CHECK (qty_ordered > 0),
    CONSTRAINT ck_po_lines_qty_received_bounds
        CHECK (0 <= qty_received AND qty_received <= qty_ordered)
);

CREATE INDEX ix_po_lines_po_id ON po_lines (po_id);
CREATE INDEX ix_po_lines_item_id ON po_lines (item_id);

CREATE TABLE goods_receipts (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    gr_number VARCHAR(50) NOT NULL,
    po_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    received_date DATE NOT NULL,
    notes TEXT,
    posted_at TIMESTAMPTZ,
    posted_by BIGINT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_goods_receipts PRIMARY KEY (id),
    CONSTRAINT uq_goods_receipts_gr_number UNIQUE (gr_number),
    CONSTRAINT uq_goods_receipts_id_po_wh UNIQUE (id, po_id, warehouse_id),
    CONSTRAINT fk_goods_receipts_po_warehouse
        FOREIGN KEY (po_id, warehouse_id)
        REFERENCES purchase_orders (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_goods_receipts_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_goods_receipts_posted_by
        FOREIGN KEY (posted_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_goods_receipts_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_goods_receipts_status CHECK (
        status IN ('DRAFT', 'POSTED', 'CANCELLED')
    )
);

CREATE INDEX ix_goods_receipts_po_id ON goods_receipts (po_id);
CREATE INDEX ix_goods_receipts_warehouse_id ON goods_receipts (warehouse_id);
CREATE INDEX ix_goods_receipts_status ON goods_receipts (status);

CREATE TABLE gr_lines (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    gr_id BIGINT NOT NULL,
    po_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    po_line_id BIGINT NOT NULL,
    location_id BIGINT NOT NULL,
    qty_received NUMERIC(18, 4) NOT NULL,
    notes TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_gr_lines PRIMARY KEY (id),
    CONSTRAINT uq_gr_lines_gr_po_line_loc
        UNIQUE (gr_id, po_line_id, location_id),
    CONSTRAINT fk_gr_lines_gr_header
        FOREIGN KEY (gr_id, po_id, warehouse_id)
        REFERENCES goods_receipts (id, po_id, warehouse_id) ON DELETE CASCADE,
    CONSTRAINT fk_gr_lines_po_line
        FOREIGN KEY (po_line_id, po_id)
        REFERENCES po_lines (id, po_id) ON DELETE RESTRICT,
    CONSTRAINT fk_gr_lines_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_gr_lines_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_gr_lines_qty_positive
        CHECK (qty_received > 0)
);

CREATE INDEX ix_gr_lines_gr_id ON gr_lines (gr_id);
CREATE INDEX ix_gr_lines_po_line_id ON gr_lines (po_line_id);
CREATE INDEX ix_gr_lines_location_id ON gr_lines (location_id);

