-- ============================================================================
-- 014_enhance_audit_logs.sql
-- Tahap 14 (Poin 3): Penyempurnaan pencatatan log_audit (status aksi, user_agent,
-- request_id korelasi, dan details JSONB) tanpa melanggar imutabilitas append-only.
-- ============================================================================

ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    ADD COLUMN IF NOT EXISTS user_agent VARCHAR(512),
    ADD COLUMN IF NOT EXISTS request_id VARCHAR(128),
    ADD COLUMN IF NOT EXISTS details JSONB;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_audit_logs_status'
          AND conrelid = 'audit_logs'::regclass
    ) THEN
        ALTER TABLE audit_logs
            ADD CONSTRAINT ck_audit_logs_status
            CHECK (status IN ('SUCCESS', 'FAILED'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_audit_logs_status ON audit_logs (status);
CREATE INDEX IF NOT EXISTS ix_audit_logs_request_id ON audit_logs (request_id);
