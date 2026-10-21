-- ============================================================================
-- 008_seed_roles_permissions.sql
-- Rujukan PRD: Bagian 3, 3.1 (Matriks Permission), Lampiran A
-- Seed 5 peran dan 24 kode permission beserta pemetaannya.
-- ============================================================================

INSERT INTO roles (name, description) VALUES
    ('Super Admin',       'Administrator sistem TI dengan akses penuh ke seluruh modul dan seluruh gudang'),
    ('Warehouse Manager', 'Kepala operasional gudang; menyetujui Transfer & Opname, menutup PO, memantau stok'),
    ('Purchasing Staff',  'Staf pengadaan/pembelian; mengelola master barang/pemasok dan siklus PO'),
    ('Warehouse Staff',   'Operator operasional gudang pada gudang yang ditugaskan (GR, Transfer, hitung Opname)'),
    ('Auditor',           'Pemeriksa internal / manajemen dengan akses baca ke seluruh modul dan Audit Log')
ON CONFLICT (name) DO NOTHING;

INSERT INTO permissions (code, description) VALUES
    ('user:manage',      'Kelola pengguna, role/permission, penugasan gudang'),
    ('warehouse:manage', 'Kelola gudang & konfigurasinya'),
    ('location:manage',  'Kelola lokasi penyimpanan'),
    ('master:manage',    'Kelola kategori, UoM, barang, pemasok'),
    ('master:read',      'Baca master data'),
    ('po:create',        'Buat/ubah PO DRAFT, batalkan PO DRAFT'),
    ('po:issue',         'Terbitkan PO'),
    ('po:cancel',        'Batalkan PO ISSUED'),
    ('po:close',         'Tutup PO'),
    ('po:read',          'Baca PO'),
    ('gr:manage',        'Buat, ubah, posting, batalkan GR'),
    ('gr:read',          'Baca GR'),
    ('transfer:create',  'Buat/ubah/batalkan Transfer DRAFT'),
    ('transfer:approve', 'Setujui / batalkan Transfer'),
    ('transfer:ship',    'Kirim Transfer (SHIPPED)'),
    ('transfer:receive', 'Terima Transfer (RECEIVED)'),
    ('transfer:read',    'Baca Transfer'),
    ('opname:manage',    'Buat, mulai, batalkan sesi Opname'),
    ('opname:count',     'Input hitung fisik & ajukan persetujuan'),
    ('opname:approve',   'Setujui / tolak hasil Opname'),
    ('opname:read',      'Baca Opname'),
    ('stock:read',       'Baca saldo stok'),
    ('ledger:read',      'Baca Stock Movement Ledger'),
    ('audit:read',       'Baca Audit Log')
ON CONFLICT (code) DO NOTHING;

-- 1. Super Admin: seluruh 24 permission
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'Super Admin'
ON CONFLICT DO NOTHING;

-- 2. Warehouse Manager
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'location:manage',
    'master:read',
    'po:close',
    'po:read',
    'gr:read',
    'transfer:approve',
    'transfer:read',
    'opname:manage',
    'opname:approve',
    'opname:read',
    'stock:read',
    'ledger:read'
)
WHERE r.name = 'Warehouse Manager'
ON CONFLICT DO NOTHING;

-- 3. Purchasing Staff
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'master:manage',
    'master:read',
    'po:create',
    'po:issue',
    'po:cancel',
    'po:close',
    'po:read',
    'gr:read',
    'stock:read'
)
WHERE r.name = 'Purchasing Staff'
ON CONFLICT DO NOTHING;

-- 4. Warehouse Staff
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'master:read',
    'po:read',
    'gr:manage',
    'gr:read',
    'transfer:create',
    'transfer:ship',
    'transfer:receive',
    'transfer:read',
    'opname:count',
    'opname:read',
    'stock:read',
    'ledger:read'
)
WHERE r.name = 'Warehouse Staff'
ON CONFLICT DO NOTHING;

-- 5. Auditor
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'master:read',
    'po:read',
    'gr:read',
    'transfer:read',
    'opname:read',
    'stock:read',
    'ledger:read',
    'audit:read'
)
WHERE r.name = 'Auditor'
ON CONFLICT DO NOTHING;

