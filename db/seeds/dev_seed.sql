-- ============================================================================
-- dev_seed.sql — Data contoh untuk pengembangan lokal (Master Data awal)
-- Catatan: Jalankan setelah migrasi 001 s.d. 008 selesai diterapkan.
-- ============================================================================

INSERT INTO categories (name, description, is_active) VALUES
    ('Elektronik', 'Perangkat dan komponen elektronik', TRUE),
    ('Bahan Baku', 'Material produksi dan bahan dasar', TRUE),
    ('Kemasan',    'Kardus, plastik pelindung, dan palet', TRUE)
ON CONFLICT (name) DO NOTHING;

INSERT INTO uoms (code, name, allow_decimal, is_active) VALUES
    ('PCS', 'Pieces / Unit', FALSE, TRUE),
    ('BOX', 'Box / Kotak',   FALSE, TRUE),
    ('KG',  'Kilogram',      TRUE,  TRUE),
    ('LTR', 'Liter',         TRUE,  TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO suppliers (code, name, contact_person, phone, email, address, is_active) VALUES
    ('SUP-001', 'PT Nusantara Logistik Makmur', 'Budi Santoso', '021-5550101', 'sales@nusantaralogistik.co.id', 'Kawasan Industri Jababeka, Cikarang', TRUE),
    ('SUP-002', 'CV Mitra Teknik Presisi',      'Siti Aminah',  '021-5550202', 'order@mitrateknik.co.id',       'Jl. Raya Daan Mogot KM 14, Jakarta Barat', TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO warehouses (code, name, address, allow_negative_stock, is_active) VALUES
    ('WH-JKT', 'Gudang Pusat Jakarta',  'Kawasan Industri Pulogadung, Jakarta Timur', FALSE, TRUE),
    ('WH-SBY', 'Gudang Cabang Surabaya', 'Kawasan Industri Rungkut (SIER), Surabaya', FALSE, TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO storage_locations (warehouse_id, code, name, is_active)
SELECT w.id, loc.code, loc.name, TRUE
FROM warehouses w
CROSS JOIN (
    VALUES
        ('A-01-01', 'Rak A Baris 1 Bin 1'),
        ('A-01-02', 'Rak A Baris 1 Bin 2'),
        ('B-01-01', 'Rak B Baris 1 Bin 1')
) AS loc(code, name)
WHERE w.code IN ('WH-JKT', 'WH-SBY')
ON CONFLICT (warehouse_id, code) DO NOTHING;

INSERT INTO items (sku, name, description, category_id, uom_id, is_active)
SELECT
    v.sku,
    v.name,
    v.description,
    c.id,
    u.id,
    TRUE
FROM (
    VALUES
        ('SKU-EL-001', 'Scanner Barcode Industrial 2D', 'Scanner barcode kabel & nirkabel', 'Elektronik', 'PCS'),
        ('SKU-BB-001', 'Biji Plastik Polypropylene',    'Bahan baku resin PP murni',       'Bahan Baku', 'KG'),
        ('SKU-KM-001', 'Kardus Double Wall 60x40x40',   'Kardus pengemasan tebal',         'Kemasan',    'PCS')
) AS v(sku, name, description, cat_name, uom_code)
JOIN categories c ON c.name = v.cat_name
JOIN uoms u ON u.code = v.uom_code
ON CONFLICT (sku) DO NOTHING;

