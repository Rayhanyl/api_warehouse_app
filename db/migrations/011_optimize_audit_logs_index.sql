-- ============================================================================
-- 011_optimize_audit_logs_index.sql
-- Optimasi index komposit pada audit_logs dan stock_movements untuk paginasi
-- dan pemfilteran rentang waktu (created_at DESC, id DESC) pada volume data besar.
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at_id
    ON audit_logs (created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS ix_stock_movements_created_at_id
    ON stock_movements (created_at DESC, id DESC);

