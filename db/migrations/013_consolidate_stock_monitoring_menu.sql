-- ============================================================================
-- Migrasi 013: Konsolidasi Menu Persediaan menjadi 1 Menu Utama (Monitoring Saldo Stok)
-- Sesuai Arsitektur UX Opsi B (PRD_GENERAL.md §6.6 & PRD_FRONTEND.md §3.7)
-- ============================================================================

-- 1. Perbarui menu root 'inventory' menjadi menu langsung 'Monitoring Saldo Stok'
UPDATE menus
SET
    name = 'Monitoring Saldo Stok',
    path = '/stock',
    icon = 'boxes',
    permission_id = (SELECT id FROM permissions WHERE code = 'stock:read'),
    parent_id = NULL,
    sort_order = 30,
    is_active = TRUE
WHERE code = 'inventory';

-- 2. Nonaktifkan submenu turunan di bawah 'inventory' agar pohon navigasi sidebar bersih
-- Seluruh 5 dimensi saldo stok disajikan terpadu pada /stock via tab segmented horizontal
UPDATE menus
SET is_active = FALSE
WHERE code IN ('stock_by_location', 'stock_by_warehouse', 'stock_summary', 'stock_ledger');
