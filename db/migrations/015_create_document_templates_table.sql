-- ============================================================================
-- 015_create_document_templates_table.sql
-- Tahap 17 (Poin 10): Pengaturan template layout dokumen cetak modular
-- berbasis database (GOODS_RECEIPT, STOCK_TRANSFER, PURCHASE_ORDER)
-- beserta menu administrasi Template Dokumen.
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_templates (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    document_type VARCHAR(50) NOT NULL,
    document_title VARCHAR(150) NOT NULL,
    company_name VARCHAR(150) NOT NULL,
    company_address TEXT,
    company_contact VARCHAR(120),
    logo_url VARCHAR(255),
    logo_position VARCHAR(20) NOT NULL DEFAULT 'LEFT',
    logo_size VARCHAR(20) NOT NULL DEFAULT 'MEDIUM',
    header_notes TEXT,
    footer_notes TEXT,
    paper_size VARCHAR(20) NOT NULL DEFAULT 'A4',
    orientation VARCHAR(20) NOT NULL DEFAULT 'PORTRAIT',
    margin_mm NUMERIC(5, 2) NOT NULL DEFAULT 12.00,
    show_barcode BOOLEAN NOT NULL DEFAULT TRUE,
    show_line_notes BOOLEAN NOT NULL DEFAULT TRUE,
    show_company_contact BOOLEAN NOT NULL DEFAULT TRUE,
    section_order JSONB NOT NULL DEFAULT '["HEADER","METADATA","TABLE","NOTES","SIGNATURES"]'::jsonb,
    table_columns JSONB NOT NULL,
    signature_layout JSONB NOT NULL,
    updated_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_document_templates PRIMARY KEY (id),
    CONSTRAINT uq_document_templates_type UNIQUE (document_type),
    CONSTRAINT ck_document_templates_type
        CHECK (document_type IN ('GOODS_RECEIPT', 'STOCK_TRANSFER', 'PURCHASE_ORDER')),
    CONSTRAINT ck_document_templates_logo_position
        CHECK (logo_position IN ('LEFT', 'CENTER', 'RIGHT')),
    CONSTRAINT ck_document_templates_logo_size
        CHECK (logo_size IN ('SMALL', 'MEDIUM', 'LARGE')),
    CONSTRAINT ck_document_templates_paper_size
        CHECK (paper_size IN ('A4', 'LETTER', 'F4')),
    CONSTRAINT ck_document_templates_orientation
        CHECK (orientation IN ('PORTRAIT', 'LANDSCAPE')),
    CONSTRAINT ck_document_templates_margin_mm
        CHECK (margin_mm >= 4 AND margin_mm <= 40)
);

CREATE INDEX IF NOT EXISTS ix_document_templates_type ON document_templates (document_type);

-- Seed bawaan 3 jenis dokumen operasional WMS (idempoten)
INSERT INTO document_templates (
    document_type,
    document_title,
    company_name,
    company_address,
    company_contact,
    logo_url,
    logo_position,
    logo_size,
    header_notes,
    footer_notes,
    paper_size,
    orientation,
    margin_mm,
    show_barcode,
    show_line_notes,
    show_company_contact,
    section_order,
    table_columns,
    signature_layout
)
VALUES
(
    'GOODS_RECEIPT',
    'BUKTI PENERIMAAN BARANG (GOODS RECEIPT NOTE)',
    'JEJAKSTOK WAREHOUSE MANAGEMENT SYSTEM',
    'Jl. Industri Logistik Terpadu No. 1, Jakarta',
    'Telp: (021) 555-0190 | Email: warehouse@jejakstok.local',
    NULL,
    'LEFT',
    'MEDIUM',
    NULL,
    'Dokumen ini diterbitkan secara resmi oleh sistem WMS sebagai bukti sah penerimaan fisik barang.',
    'A4',
    'PORTRAIT',
    12.00,
    TRUE,
    TRUE,
    TRUE,
    '["HEADER","METADATA","TABLE","NOTES","SIGNATURES"]'::jsonb,
    '[
        {"key":"no","label":"No","visible":true},
        {"key":"sku_barcode","label":"SKU / Barcode","visible":true},
        {"key":"item_name","label":"Nama Barang","visible":true},
        {"key":"location","label":"Lokasi Simpan","visible":true},
        {"key":"qty_received","label":"Qty Diterima","visible":true},
        {"key":"uom","label":"Satuan","visible":true},
        {"key":"notes","label":"Catatan Baris","visible":true}
    ]'::jsonb,
    '[
        {"title":"Diserahkan Oleh","subtitle":"Pengirim / Ekspedisi Pemasok","placeholder":"( Nama Terang & Tanda Tangan )"},
        {"title":"Diterima & Diperiksa Oleh","subtitle":"Staf / Admin Gudang","placeholder":"( Nama Terang & Tanda Tangan )"},
        {"title":"Diketahui Oleh","subtitle":"Kepala Gudang / Supervisor","placeholder":"( Nama Terang & Stempel Gudang )"}
    ]'::jsonb
),
(
    'STOCK_TRANSFER',
    'SURAT JALAN TRANSFER STOK',
    'JEJAKSTOK WAREHOUSE MANAGEMENT SYSTEM',
    'Jl. Industri Logistik Terpadu No. 1, Jakarta',
    'Telp: (021) 555-0190 | Email: warehouse@jejakstok.local',
    NULL,
    'LEFT',
    'MEDIUM',
    NULL,
    'Harap periksa fisik barang dan segel kemasan sebelum menandatangani berita acara penerimaan.',
    'A4',
    'PORTRAIT',
    12.00,
    TRUE,
    TRUE,
    TRUE,
    '["HEADER","METADATA","TABLE","NOTES","SIGNATURES"]'::jsonb,
    '[
        {"key":"no","label":"No","visible":true},
        {"key":"sku_barcode","label":"SKU / Barcode","visible":true},
        {"key":"item_name","label":"Nama Barang","visible":true},
        {"key":"uom","label":"Satuan","visible":true},
        {"key":"qty_shipped","label":"Qty Kirim","visible":true},
        {"key":"qty_received","label":"Qty Diterima","visible":true},
        {"key":"variance","label":"Selisih / Keterangan Cek Fisik","visible":true}
    ]'::jsonb,
    '[
        {"title":"Diserahkan Oleh","subtitle":"Petugas Gudang Asal","placeholder":"( Nama Terang & Tanda Tangan )"},
        {"title":"Dibawa Oleh","subtitle":"Pengemudi / Kurir / Ekspedisi","placeholder":"( Nama Terang & No. Polisi )"},
        {"title":"Diterima Oleh","subtitle":"Petugas Gudang / Toko Tujuan","placeholder":"( Nama Terang & Stempel Cabang )"}
    ]'::jsonb
),
(
    'PURCHASE_ORDER',
    'PURCHASE ORDER (SURAT PESANAN PEMBELIAN)',
    'JEJAKSTOK WAREHOUSE MANAGEMENT SYSTEM',
    'Jl. Industri Logistik Terpadu No. 1, Jakarta',
    'Telp: (021) 555-0190 | Email: procurement@jejakstok.local',
    NULL,
    'LEFT',
    'MEDIUM',
    'Mohon cantumkan nomor PO pada surat jalan dan faktur pengiriman barang.',
    'Pesanan sah apabila telah ditandatangani oleh pejabat berwenang dan dikirim sesuai jadwal.',
    'A4',
    'PORTRAIT',
    12.00,
    TRUE,
    TRUE,
    TRUE,
    '["HEADER","METADATA","TABLE","NOTES","SIGNATURES"]'::jsonb,
    '[
        {"key":"no","label":"No","visible":true},
        {"key":"sku_barcode","label":"Kode SKU","visible":true},
        {"key":"item_name","label":"Nama Barang","visible":true},
        {"key":"uom","label":"Satuan","visible":true},
        {"key":"qty_ordered","label":"Qty Pesanan","visible":true},
        {"key":"qty_received","label":"Qty Diterima","visible":true},
        {"key":"notes","label":"Catatan Baris","visible":true}
    ]'::jsonb,
    '[
        {"title":"Dibuat Oleh","subtitle":"Staf Pengadaan / Purchasing","placeholder":"( Nama Terang & Tanda Tangan )"},
        {"title":"Disetujui Oleh","subtitle":"Manajer Gudang / Operasional","placeholder":"( Nama Terang & Tanda Tangan )"},
        {"title":"Diterima Pemasok","subtitle":"Konfirmasi Supplier","placeholder":"( Nama Terang & Stempel Perusahaan )"}
    ]'::jsonb
)
ON CONFLICT (document_type) DO NOTHING;

-- Tambah submenu Template Dokumen di bawah grup Administrasi & Keamanan
INSERT INTO menus (code, name, path, icon, parent_id, sort_order, permission_id, is_active)
SELECT
    'admin_document_templates',
    'Template Dokumen',
    '/admin/document-templates',
    'printer',
    parent_menu.id,
    35,
    perm.id,
    TRUE
FROM menus parent_menu
LEFT JOIN permissions perm ON perm.code = 'user:manage'
WHERE parent_menu.code = 'administration'
ON CONFLICT (code) DO NOTHING;

-- Hak akses role aplikasi wms_app
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wms_app') THEN
        GRANT SELECT, INSERT, UPDATE ON TABLE document_templates TO wms_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO wms_app;
    END IF;
END
$$;
