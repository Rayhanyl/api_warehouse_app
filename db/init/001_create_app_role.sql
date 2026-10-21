-- ============================================================================
-- Inisialisasi awal cluster PostgreSQL (dijalankan sekali oleh initdb.d)
-- Membuat role aplikasi `wms_app` (bukan superuser, bukan pemilik tabel)
-- dan database pengujian `wms_test`.
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wms_app') THEN
        CREATE ROLE wms_app WITH
            LOGIN
            PASSWORD 'wms_app_pass'
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE;
    END IF;
END
$$;

-- Beri hak koneksi ke database utama
GRANT CONNECT ON DATABASE wms TO wms_app;

-- Buat database pengujian wms_test untuk pytest
SELECT 'CREATE DATABASE wms_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'wms_test')\gexec

GRANT CONNECT ON DATABASE wms_test TO wms_app;

