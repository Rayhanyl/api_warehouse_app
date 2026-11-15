-- ============================================================================
-- 018_rbac_multi_level_approval_and_sod.sql
-- Rujukan: Tahap 34 (Multi-Level Approval PO & Stock Opname + Ekspansi Role)
--          Tahap 38 (Segregation of Duties: gr:create / gr:post & maker-checker)
-- ============================================================================

-- 1. Tambah permission baru (pemecahan GR + Multi-Level Approval PO & Opname + Settings)
INSERT INTO permissions (code, description) VALUES
    ('gr:create',          'Buat, ubah, batalkan draft Goods Receipt'),
    ('gr:post',            'Posting Goods Receipt menjadi stok final'),
    ('po:approve_l1',      'Persetujuan Purchase Order Level 1'),
    ('po:approve_l2',      'Persetujuan Purchase Order Level 2 (di atas ambang nominal)'),
    ('opname:approve_l1',  'Persetujuan Stock Opname Level 1 (Supervisor)'),
    ('opname:approve_l2',  'Persetujuan Stock Opname Level 2 / Final (Manager)'),
    ('settings:manage',    'Kelola konfigurasi ambang approval & pengaturan sistem')
ON CONFLICT (code) DO NOTHING;

-- 2. Tambah 2 role jabatan baku baru
INSERT INTO roles (name, description) VALUES
    ('Warehouse Supervisor', 'Supervisor operasional gudang; memposting GR serta menyetujui Transfer & Opname Tahap 1'),
    ('Procurement Manager',  'Manajer pengadaan & keuangan; menyetujui PO Level 1 & Level 2 serta mengawasi pengadaan bernilai besar')
ON CONFLICT (name) DO NOTHING;

-- 3. Migrasikan pemetaan lama (gr:manage -> gr:create/gr:post, opname:approve -> L1/L2)
INSERT INTO role_permissions (role_id, permission_id)
SELECT rp.role_id, p_new.id
FROM role_permissions rp
JOIN permissions p_old ON p_old.id = rp.permission_id AND p_old.code = 'gr:manage'
JOIN permissions p_new ON p_new.code = 'gr:create'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT rp.role_id, p_new.id
FROM role_permissions rp
JOIN permissions p_old ON p_old.id = rp.permission_id AND p_old.code = 'opname:approve'
JOIN permissions p_new ON p_new.code IN ('opname:approve_l1', 'opname:approve_l2')
ON CONFLICT DO NOTHING;

-- Hapus izin legacy gr:manage & opname:approve setelah migrasi ke permission tergranularisasi
DELETE FROM role_permissions
WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('gr:manage', 'opname:approve'));

DELETE FROM permissions WHERE code IN ('gr:manage', 'opname:approve');

-- 4. Lengkapi hak akses masing-masing role
-- Super Admin: seluruh permission
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'Super Admin'
ON CONFLICT DO NOTHING;

-- Warehouse Manager: gr:create, gr:post, po:approve_l1, opname:approve_l1, opname:approve_l2
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'gr:create',
    'gr:post',
    'po:approve_l1',
    'opname:approve_l1',
    'opname:approve_l2'
)
WHERE r.name = 'Warehouse Manager'
ON CONFLICT DO NOTHING;

-- Warehouse Supervisor
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'location:manage',
    'master:read',
    'po:read',
    'gr:create',
    'gr:post',
    'gr:read',
    'transfer:create',
    'transfer:approve',
    'transfer:ship',
    'transfer:receive',
    'transfer:read',
    'opname:manage',
    'opname:count',
    'opname:approve_l1',
    'opname:read',
    'stock:read',
    'ledger:read'
)
WHERE r.name = 'Warehouse Supervisor'
ON CONFLICT DO NOTHING;

-- Procurement Manager
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'master:manage',
    'master:read',
    'po:create',
    'po:issue',
    'po:approve_l1',
    'po:approve_l2',
    'po:cancel',
    'po:close',
    'po:read',
    'gr:read',
    'stock:read'
)
WHERE r.name = 'Procurement Manager'
ON CONFLICT DO NOTHING;

-- 5. Pengaturan sistem (threshold approval PO)
CREATE TABLE IF NOT EXISTS app_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_by BIGINT REFERENCES users (id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO app_settings (key, value, description) VALUES
    (
        'po_l2_approval_threshold',
        '10000000',
        'Ambang nominal total PO (IDR); di atas nilai ini wajib persetujuan Level 2 (Procurement Manager / Super Admin).'
    )
ON CONFLICT (key) DO NOTHING;

-- 6. Riwayat persetujuan & penolakan berjenjang
CREATE TABLE IF NOT EXISTS approval_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_type VARCHAR(20) NOT NULL CHECK (doc_type IN ('PO', 'OPNAME')),
    doc_id BIGINT NOT NULL,
    approval_level SMALLINT NOT NULL CHECK (approval_level IN (0, 1, 2)),
    action VARCHAR(20) NOT NULL CHECK (action IN ('SUBMITTED', 'APPROVED', 'REJECTED')),
    actor_id BIGINT REFERENCES users (id) ON DELETE RESTRICT,
    actor_name VARCHAR(150) NOT NULL,
    actor_role VARCHAR(100) NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_approval_logs_doc ON approval_logs (doc_type, doc_id, id ASC);

-- 7. Pembaruan struktur Purchase Order & baris PO (harga opsional & tracking approval)
ALTER TABLE po_lines
    ADD COLUMN IF NOT EXISTS unit_price NUMERIC(18, 2) NOT NULL DEFAULT 0.00;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_po_lines_unit_price_non_negative'
    ) THEN
        ALTER TABLE po_lines
            ADD CONSTRAINT ck_po_lines_unit_price_non_negative CHECK (unit_price >= 0);
    END IF;
END $$;

ALTER TABLE purchase_orders
    ADD COLUMN IF NOT EXISTS total_amount NUMERIC(18, 2) NOT NULL DEFAULT 0.00,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
    ADD COLUMN IF NOT EXISTS submitted_by BIGINT REFERENCES users (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS l1_approved_by BIGINT REFERENCES users (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS l1_approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS l2_approved_by BIGINT REFERENCES users (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS l2_approved_at TIMESTAMPTZ;

ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS ck_purchase_orders_status;
ALTER TABLE purchase_orders
    ADD CONSTRAINT ck_purchase_orders_status CHECK (
        status IN (
            'DRAFT',
            'WAITING_L1_APPROVAL',
            'WAITING_L2_APPROVAL',
            'ISSUED',
            'PARTIALLY_RECEIVED',
            'RECEIVED',
            'CLOSED',
            'CANCELLED'
        )
    );

-- 8. Pembaruan struktur Stock Opname (tracking L1 & L2)
ALTER TABLE stock_opnames
    ADD COLUMN IF NOT EXISTS l1_approved_by BIGINT REFERENCES users (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS l1_approved_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS l2_approved_by BIGINT REFERENCES users (id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS l2_approved_at TIMESTAMPTZ;

ALTER TABLE stock_opnames DROP CONSTRAINT IF EXISTS ck_stock_opnames_status;
ALTER TABLE stock_opnames
    ADD CONSTRAINT ck_stock_opnames_status CHECK (
        status IN (
            'DRAFT',
            'IN_PROGRESS',
            'WAITING_L1_APPROVAL',
            'WAITING_L2_APPROVAL',
            'WAITING_APPROVAL',
            'COMPLETED',
            'CANCELLED'
        )
    );

UPDATE stock_opnames
SET status = 'WAITING_L1_APPROVAL'
WHERE status = 'WAITING_APPROVAL';

DROP INDEX IF EXISTS ix_stock_opnames_active_scope;
CREATE INDEX ix_stock_opnames_active_scope
    ON stock_opnames (warehouse_id, location_id)
    WHERE status IN ('IN_PROGRESS', 'WAITING_L1_APPROVAL', 'WAITING_L2_APPROVAL', 'WAITING_APPROVAL');

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wms_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE app_settings, approval_logs TO wms_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO wms_app;
    END IF;
END $$;
