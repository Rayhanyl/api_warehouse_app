-- ============================================================================
-- 007_append_only_guards.sql
-- Rujukan PRD: Bagian 6.4, 7.5, AC-08
-- Fungsi & Trigger imutabilitas (append-only) pada stock_movements dan audit_logs,
-- serta pengaturan hak akses role aplikasi `wms_app` (REVOKE UPDATE, DELETE, TRUNCATE).
-- ============================================================================

CREATE OR REPLACE FUNCTION prevent_append_only_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Tabel % bersifat append-only; operasi % tidak diizinkan.', TG_TABLE_NAME, TG_OP
        USING ERRCODE = '42501';
END;
$$;

CREATE TRIGGER trg_stock_movements_immutable
BEFORE UPDATE OR DELETE ON stock_movements
FOR EACH ROW
EXECUTE FUNCTION prevent_append_only_mutation();

CREATE TRIGGER trg_audit_logs_immutable
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW
EXECUTE FUNCTION prevent_append_only_mutation();

-- Pengaturan hak akses untuk role aplikasi (wms_app)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wms_app') THEN
        GRANT USAGE ON SCHEMA public TO wms_app;

        -- Beri hak CRUD standar pada seluruh tabel operasional
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO wms_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO wms_app;

        -- Cabut UPDATE, DELETE, TRUNCATE pada tabel append-only dan tabel migrasi (PRD 6.4 & AC-08)
        REVOKE UPDATE, DELETE, TRUNCATE ON TABLE stock_movements, audit_logs FROM wms_app;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE schema_migrations FROM wms_app;
    END IF;
END
$$;

