-- ============================================================================
-- 009_create_menu_tables.sql
-- Rujukan PRD: Bagian 2.1, 3.1, FR-01, 7.5, Lampiran A, Lampiran C (#16)
-- Tabel: menus (hierarki menu navigasi dinamis berbasis permission_id)
-- beserta data awal (seed) struktur menu modul WMS.
-- ============================================================================

CREATE TABLE menus (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    path VARCHAR(150) NOT NULL,
    icon VARCHAR(50),
    parent_id BIGINT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    permission_id BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_menus PRIMARY KEY (id),
    CONSTRAINT uq_menus_code UNIQUE (code),
    CONSTRAINT fk_menus_parent_id
        FOREIGN KEY (parent_id) REFERENCES menus (id) ON DELETE RESTRICT,
    CONSTRAINT fk_menus_permission_id
        FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE SET NULL,
    CONSTRAINT ck_menus_no_self_parent
        CHECK (parent_id IS NULL OR parent_id <> id)
);

CREATE INDEX ix_menus_parent_id ON menus (parent_id);
CREATE INDEX ix_menus_permission_id ON menus (permission_id);
CREATE INDEX ix_menus_sort_order ON menus (sort_order, id);
CREATE INDEX ix_menus_is_active ON menus (is_active);

-- ============================================================================
-- Seed Menu Tingkat Utama (Root / Group Menus)
-- ============================================================================
INSERT INTO menus (code, name, path, icon, parent_id, sort_order, permission_id, is_active)
VALUES
    ('dashboard',      'Dashboard',                 '/dashboard',  'layout-dashboard', NULL, 10, NULL, TRUE),
    ('master',         'Master Data',               '/master',     'database',         NULL, 20, NULL, TRUE),
    ('inventory',      'Stok & Buku Besar',         '/stock',      'boxes',            NULL, 30, NULL, TRUE),
    ('purchasing',     'Pengadaan & Penerimaan',    '/purchasing', 'shopping-cart',    NULL, 40, NULL, TRUE),
    ('warehouse_ops',  'Operasional Gudang',        '/operations', 'warehouse',        NULL, 50, NULL, TRUE),
    ('administration', 'Administrasi & Keamanan',   '/admin',      'shield',           NULL, 60, NULL, TRUE)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Seed Submenu di bawah Master Data ('master')
-- ============================================================================
INSERT INTO menus (code, name, path, icon, parent_id, sort_order, permission_id, is_active)
SELECT
    v.code,
    v.name,
    v.path,
    v.icon,
    parent_menu.id,
    v.sort_order,
    perm.id,
    TRUE
FROM (
    VALUES
        ('master_categories', 'Kategori Barang',    '/master/categories', 'folder-tree', 10, 'master:read'),
        ('master_uoms',       'Satuan Ukur (UoM)',  '/master/uoms',       'scale',       20, 'master:read'),
        ('master_suppliers',  'Pemasok (Supplier)', '/master/suppliers',  'truck',       30, 'master:read'),
        ('master_items',      'Barang (SKU)',       '/master/items',      'package',     40, 'master:read'),
        ('master_warehouses', 'Gudang',             '/master/warehouses', 'building-2',  50, 'master:read'),
        ('master_locations',  'Lokasi Penyimpanan', '/master/locations',  'map-pin',     60, 'master:read')
) AS v (code, name, path, icon, sort_order, perm_code)
JOIN menus parent_menu ON parent_menu.code = 'master'
LEFT JOIN permissions perm ON perm.code = v.perm_code
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Seed Submenu di bawah Stok & Buku Besar ('inventory')
-- ============================================================================
INSERT INTO menus (code, name, path, icon, parent_id, sort_order, permission_id, is_active)
SELECT
    v.code,
    v.name,
    v.path,
    v.icon,
    parent_menu.id,
    v.sort_order,
    perm.id,
    TRUE
FROM (
    VALUES
        ('stock_by_location',  'Saldo Stok per Lokasi',        '/stock/by-location',  'layers',      10, 'stock:read'),
        ('stock_by_warehouse', 'Saldo Stok per Gudang',        '/stock/by-warehouse', 'warehouse',   20, 'stock:read'),
        ('stock_summary',      'Ringkasan Stok Lintas Gudang', '/stock/summary',      'bar-chart-3', 30, 'stock:read'),
        ('stock_ledger',       'Buku Besar Stok (Ledger)',     '/stock/ledger',       'book-open',   40, 'ledger:read')
) AS v (code, name, path, icon, sort_order, perm_code)
JOIN menus parent_menu ON parent_menu.code = 'inventory'
LEFT JOIN permissions perm ON perm.code = v.perm_code
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Seed Submenu di bawah Pengadaan & Penerimaan ('purchasing')
-- ============================================================================
INSERT INTO menus (code, name, path, icon, parent_id, sort_order, permission_id, is_active)
SELECT
    v.code,
    v.name,
    v.path,
    v.icon,
    parent_menu.id,
    v.sort_order,
    perm.id,
    TRUE
FROM (
    VALUES
        ('purchase_orders', 'Purchase Order (PO)',    '/purchasing/purchase-orders', 'file-text',     10, 'po:read'),
        ('goods_receipts',  'Penerimaan Barang (GR)', '/purchasing/goods-receipts',  'package-check', 20, 'gr:read')
) AS v (code, name, path, icon, sort_order, perm_code)
JOIN menus parent_menu ON parent_menu.code = 'purchasing'
LEFT JOIN permissions perm ON perm.code = v.perm_code
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Seed Submenu di bawah Operasional Gudang ('warehouse_ops')
-- ============================================================================
INSERT INTO menus (code, name, path, icon, parent_id, sort_order, permission_id, is_active)
SELECT
    v.code,
    v.name,
    v.path,
    v.icon,
    parent_menu.id,
    v.sort_order,
    perm.id,
    TRUE
FROM (
    VALUES
        ('stock_transfers', 'Transfer Stok', '/operations/stock-transfers', 'arrow-left-right', 10, 'transfer:read'),
        ('stock_opnames',   'Stock Opname',  '/operations/stock-opnames',   'clipboard-check',  20, 'opname:read')
) AS v (code, name, path, icon, sort_order, perm_code)
JOIN menus parent_menu ON parent_menu.code = 'warehouse_ops'
LEFT JOIN permissions perm ON perm.code = v.perm_code
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Seed Submenu di bawah Administrasi & Keamanan ('administration')
-- ============================================================================
INSERT INTO menus (code, name, path, icon, parent_id, sort_order, permission_id, is_active)
SELECT
    v.code,
    v.name,
    v.path,
    v.icon,
    parent_menu.id,
    v.sort_order,
    perm.id,
    TRUE
FROM (
    VALUES
        ('admin_users',      'Manajemen Pengguna', '/admin/users',      'users',       10, 'user:manage'),
        ('admin_roles',      'Peran & Permission', '/admin/roles',      'key-round',   20, 'user:manage'),
        ('admin_menus',      'Manajemen Menu',     '/admin/menus',      'menu',        30, 'user:manage'),
        ('admin_audit_logs', 'Audit Log',          '/admin/audit-logs', 'scroll-text', 40, 'audit:read')
) AS v (code, name, path, icon, sort_order, perm_code)
JOIN menus parent_menu ON parent_menu.code = 'administration'
LEFT JOIN permissions perm ON perm.code = v.perm_code
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- Hak Akses untuk Role Aplikasi (`wms_app`)
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wms_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE menus TO wms_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO wms_app;
    END IF;
END
$$;

