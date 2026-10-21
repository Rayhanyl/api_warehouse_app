-- ============================================================================
-- 002_create_master_tables.sql
-- Rujukan PRD: Bagian 3.2, FR-02, 6.3, 6.8, 6.9, 7.5, Lampiran A
-- Tabel: categories, uoms, suppliers, items, warehouses, user_warehouses, storage_locations
-- ============================================================================

CREATE TABLE categories (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_categories PRIMARY KEY (id),
    CONSTRAINT uq_categories_name UNIQUE (name),
    CONSTRAINT fk_categories_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_categories_is_active ON categories (is_active);

CREATE TABLE uoms (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(60) NOT NULL,
    allow_decimal BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_uoms PRIMARY KEY (id),
    CONSTRAINT uq_uoms_code UNIQUE (code),
    CONSTRAINT fk_uoms_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_uoms_is_active ON uoms (is_active);

CREATE TABLE suppliers (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(150) NOT NULL,
    contact_person VARCHAR(120),
    phone VARCHAR(30),
    email VARCHAR(255),
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_suppliers PRIMARY KEY (id),
    CONSTRAINT uq_suppliers_code UNIQUE (code),
    CONSTRAINT fk_suppliers_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_suppliers_name ON suppliers (name);
CREATE INDEX ix_suppliers_is_active ON suppliers (is_active);

CREATE TABLE items (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    sku VARCHAR(64) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category_id BIGINT NOT NULL,
    uom_id BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_items PRIMARY KEY (id),
    CONSTRAINT uq_items_sku UNIQUE (sku),
    CONSTRAINT fk_items_category_id
        FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE RESTRICT,
    CONSTRAINT fk_items_uom_id
        FOREIGN KEY (uom_id) REFERENCES uoms (id) ON DELETE RESTRICT,
    CONSTRAINT fk_items_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_items_name ON items (name);
CREATE INDEX ix_items_category_id ON items (category_id);
CREATE INDEX ix_items_uom_id ON items (uom_id);
CREATE INDEX ix_items_is_active ON items (is_active);

CREATE TABLE warehouses (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(150) NOT NULL,
    address TEXT,
    allow_negative_stock BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_warehouses PRIMARY KEY (id),
    CONSTRAINT uq_warehouses_code UNIQUE (code),
    CONSTRAINT fk_warehouses_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_warehouses_is_active ON warehouses (is_active);

CREATE TABLE user_warehouses (
    user_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_warehouses PRIMARY KEY (user_id, warehouse_id),
    CONSTRAINT fk_user_warehouses_user_id
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_warehouses_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_warehouses_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_user_warehouses_warehouse_id ON user_warehouses (warehouse_id);

CREATE TABLE storage_locations (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    warehouse_id BIGINT NOT NULL,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(120) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_storage_locations PRIMARY KEY (id),
    CONSTRAINT uq_storage_locations_warehouse_code UNIQUE (warehouse_id, code),
    CONSTRAINT uq_storage_locations_id_warehouse UNIQUE (id, warehouse_id),
    CONSTRAINT fk_storage_locations_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_storage_locations_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_storage_locations_warehouse_id ON storage_locations (warehouse_id);
CREATE INDEX ix_storage_locations_is_active ON storage_locations (is_active);

