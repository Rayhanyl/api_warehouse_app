-- ============================================================================
-- 006_create_audit_sequences.sql
-- Rujukan PRD: FR-09, FR-10, 6.4, 7.5, Lampiran A
-- Tabel: audit_logs, document_sequences
-- ============================================================================

CREATE TABLE audit_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100),
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_audit_logs PRIMARY KEY (id),
    CONSTRAINT fk_audit_logs_user_id
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);
CREATE INDEX ix_audit_logs_action ON audit_logs (action);
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at DESC);

CREATE TABLE document_sequences (
    doc_type VARCHAR(10) NOT NULL,
    period CHAR(6) NOT NULL,
    last_value INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_document_sequences PRIMARY KEY (doc_type, period),
    CONSTRAINT ck_document_sequences_doc_type
        CHECK (doc_type IN ('PO', 'GR', 'TRF', 'OPN')),
    CONSTRAINT ck_document_sequences_period_format
        CHECK (period ~ '^[0-9]{6}$'),
    CONSTRAINT ck_document_sequences_last_value_non_negative
        CHECK (last_value >= 0)
);

