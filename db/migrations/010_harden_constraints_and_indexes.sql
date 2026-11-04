-- ============================================================================
-- 010_harden_constraints_and_indexes.sql
-- Rujukan PRD: Bagian 5.1, 6.3, 6.7, 6.8, 6.9, 7.5, Lampiran A
-- Penguatan integritas skema database:
--   1. Indeks unik fungsional case-insensitive (LOWER(...)) pada kode, SKU,
--      username, email, dan nama kategori.
--   2. Constraint CHECK anti-string-kosong (length(btrim(...)) > 0) pada kolom
--      teks wajib dan alasan penolakan Stock Opname.
--   3. Constraint CHECK kelengkapan metadata waktu & aktor pada setiap status
--      dokumen operasional (PO, GR, Stock Transfer, Stock Opname).
--   4. Pencabutan hak DELETE pada tabel `menus` dari role aplikasi `wms_app`
--      (selaras dengan aturan soft-delete `is_active` pada PRD 6.8).
-- ============================================================================

-- 1. Indeks Unik Fungsional Case-Insensitive (LOWER)
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower
    ON users (LOWER(username));

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
    ON users (LOWER(email));

CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name_lower
    ON categories (LOWER(name));

CREATE UNIQUE INDEX IF NOT EXISTS uq_uoms_code_lower
    ON uoms (LOWER(code));

CREATE UNIQUE INDEX IF NOT EXISTS uq_suppliers_code_lower
    ON suppliers (LOWER(code));

CREATE UNIQUE INDEX IF NOT EXISTS uq_items_sku_lower
    ON items (LOWER(sku));

CREATE UNIQUE INDEX IF NOT EXISTS uq_warehouses_code_lower
    ON warehouses (LOWER(code));

CREATE UNIQUE INDEX IF NOT EXISTS uq_storage_locations_wh_code_lower
    ON storage_locations (warehouse_id, LOWER(code));

CREATE UNIQUE INDEX IF NOT EXISTS uq_menus_code_lower
    ON menus (LOWER(code));

-- 2. Constraint CHECK Anti-String-Kosong & Batas Nilai
ALTER TABLE roles
    ADD CONSTRAINT ck_roles_name_not_blank
        CHECK (length(btrim(name)) > 0);

ALTER TABLE permissions
    ADD CONSTRAINT ck_permissions_code_not_blank
        CHECK (length(btrim(code)) > 0);

ALTER TABLE users
    ADD CONSTRAINT ck_users_username_not_blank
        CHECK (length(btrim(username)) > 0),
    ADD CONSTRAINT ck_users_email_not_blank
        CHECK (length(btrim(email)) > 0),
    ADD CONSTRAINT ck_users_full_name_not_blank
        CHECK (length(btrim(full_name)) > 0);

ALTER TABLE categories
    ADD CONSTRAINT ck_categories_name_not_blank
        CHECK (length(btrim(name)) > 0);

ALTER TABLE uoms
    ADD CONSTRAINT ck_uoms_code_not_blank
        CHECK (length(btrim(code)) > 0),
    ADD CONSTRAINT ck_uoms_name_not_blank
        CHECK (length(btrim(name)) > 0);

ALTER TABLE suppliers
    ADD CONSTRAINT ck_suppliers_code_not_blank
        CHECK (length(btrim(code)) > 0),
    ADD CONSTRAINT ck_suppliers_name_not_blank
        CHECK (length(btrim(name)) > 0);

ALTER TABLE items
    ADD CONSTRAINT ck_items_sku_not_blank
        CHECK (length(btrim(sku)) > 0),
    ADD CONSTRAINT ck_items_name_not_blank
        CHECK (length(btrim(name)) > 0);

ALTER TABLE warehouses
    ADD CONSTRAINT ck_warehouses_code_not_blank
        CHECK (length(btrim(code)) > 0),
    ADD CONSTRAINT ck_warehouses_name_not_blank
        CHECK (length(btrim(name)) > 0);

ALTER TABLE storage_locations
    ADD CONSTRAINT ck_storage_locations_code_not_blank
        CHECK (length(btrim(code)) > 0),
    ADD CONSTRAINT ck_storage_locations_name_not_blank
        CHECK (length(btrim(name)) > 0);

ALTER TABLE menus
    ADD CONSTRAINT ck_menus_code_not_blank
        CHECK (length(btrim(code)) > 0),
    ADD CONSTRAINT ck_menus_name_not_blank
        CHECK (length(btrim(name)) > 0),
    ADD CONSTRAINT ck_menus_path_format
        CHECK (length(btrim(path)) > 0 AND left(btrim(path), 1) = '/'),
    ADD CONSTRAINT ck_menus_sort_order_bounds
        CHECK (sort_order >= 0 AND sort_order <= 10000);

ALTER TABLE stock_opnames
    ADD CONSTRAINT ck_stock_opnames_rejection_reason_not_blank
        CHECK (rejection_reason IS NULL OR length(btrim(rejection_reason)) > 0);

-- 3. Constraint CHECK Kelengkapan Metadata Status Dokumen Operasional
ALTER TABLE purchase_orders
    ADD CONSTRAINT ck_purchase_orders_issued_meta
        CHECK (
            status NOT IN ('ISSUED', 'PARTIALLY_RECEIVED', 'RECEIVED')
            OR (issued_at IS NOT NULL AND issued_by IS NOT NULL)
        ),
    ADD CONSTRAINT ck_purchase_orders_closed_meta
        CHECK (
            status <> 'CLOSED'
            OR (closed_at IS NOT NULL AND closed_by IS NOT NULL)
        );

ALTER TABLE goods_receipts
    ADD CONSTRAINT ck_goods_receipts_posted_meta
        CHECK (
            status <> 'POSTED'
            OR (posted_at IS NOT NULL AND posted_by IS NOT NULL)
        );

ALTER TABLE stock_transfers
    ADD CONSTRAINT ck_stock_transfers_approved_meta
        CHECK (
            status NOT IN ('APPROVED', 'SHIPPED', 'RECEIVED')
            OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)
        ),
    ADD CONSTRAINT ck_stock_transfers_shipped_meta
        CHECK (
            status NOT IN ('SHIPPED', 'RECEIVED')
            OR (shipped_at IS NOT NULL AND shipped_by IS NOT NULL)
        ),
    ADD CONSTRAINT ck_stock_transfers_received_meta
        CHECK (
            status <> 'RECEIVED'
            OR (received_at IS NOT NULL AND received_by IS NOT NULL)
        );

ALTER TABLE stock_opnames
    ADD CONSTRAINT ck_stock_opnames_started_meta
        CHECK (
            status NOT IN ('IN_PROGRESS', 'WAITING_APPROVAL', 'COMPLETED')
            OR (started_at IS NOT NULL AND started_by IS NOT NULL)
        ),
    ADD CONSTRAINT ck_stock_opnames_submitted_meta
        CHECK (
            status NOT IN ('WAITING_APPROVAL', 'COMPLETED')
            OR (submitted_at IS NOT NULL AND submitted_by IS NOT NULL)
        ),
    ADD CONSTRAINT ck_stock_opnames_completed_meta
        CHECK (
            status <> 'COMPLETED'
            OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)
        );

-- 4. Pencabutan Hak DELETE pada Tabel `menus` dari Role Aplikasi (`wms_app`)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wms_app') THEN
        REVOKE DELETE ON TABLE menus FROM wms_app;
    END IF;
END
$$;

