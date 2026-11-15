-- ============================================================================
-- 016_enhance_po_edit_and_short_close.sql
-- Rujukan: Tahap 36 (Edit PO Draft, Cancel & Clone ISSUED, expected_delivery_date,
--          Short-Close PO di level header & per baris barang po_lines).
-- ============================================================================

ALTER TABLE purchase_orders
    ADD COLUMN IF NOT EXISTS expected_delivery_date DATE,
    ADD COLUMN IF NOT EXISTS revised_from_po_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_purchase_orders_revised_from_po_id'
    ) THEN
        ALTER TABLE purchase_orders
            ADD CONSTRAINT fk_purchase_orders_revised_from_po_id
                FOREIGN KEY (revised_from_po_id) REFERENCES purchase_orders (id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_purchase_orders_expected_delivery_date
    ON purchase_orders (expected_delivery_date)
    WHERE expected_delivery_date IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_purchase_orders_revised_from_po_id
    ON purchase_orders (revised_from_po_id)
    WHERE revised_from_po_id IS NOT NULL;

ALTER TABLE po_lines
    ADD COLUMN IF NOT EXISTS qty_closed NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    ADD COLUMN IF NOT EXISTS line_status VARCHAR(30) NOT NULL DEFAULT 'OPEN',
    ADD COLUMN IF NOT EXISTS line_closed_reason TEXT,
    ADD COLUMN IF NOT EXISTS line_closed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS line_closed_by BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_po_lines_line_closed_by'
    ) THEN
        ALTER TABLE po_lines
            ADD CONSTRAINT fk_po_lines_line_closed_by
                FOREIGN KEY (line_closed_by) REFERENCES users (id) ON DELETE RESTRICT;
    END IF;
END $$;

-- Backfill status baris PO eksisting
UPDATE po_lines
SET line_status = CASE
    WHEN qty_received >= qty_ordered THEN 'RECEIVED'
    WHEN qty_received > 0 THEN 'PARTIALLY_RECEIVED'
    ELSE 'OPEN'
END;

-- Backfill sisa baris untuk PO yang sudah berstatus CLOSED agar konsisten dengan Short-Close
UPDATE po_lines pl
SET
    qty_closed = (pl.qty_ordered - pl.qty_received),
    line_status = 'CLOSED',
    line_closed_reason = COALESCE(NULLIF(btrim(po.closed_reason), ''), 'PO ditutup sebelum migrasi 016'),
    line_closed_at = COALESCE(po.closed_at, CURRENT_TIMESTAMP),
    line_closed_by = COALESCE(po.closed_by, po.created_by)
FROM purchase_orders po
WHERE pl.po_id = po.id
  AND po.status = 'CLOSED'
  AND pl.qty_received < pl.qty_ordered;

ALTER TABLE po_lines
    DROP CONSTRAINT IF EXISTS ck_po_lines_qty_received_bounds;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_po_lines_qty_received_non_negative'
    ) THEN
        ALTER TABLE po_lines
            ADD CONSTRAINT ck_po_lines_qty_received_non_negative CHECK (qty_received >= 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_po_lines_qty_closed_non_negative'
    ) THEN
        ALTER TABLE po_lines
            ADD CONSTRAINT ck_po_lines_qty_closed_non_negative CHECK (qty_closed >= 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_po_lines_qty_bounds'
    ) THEN
        ALTER TABLE po_lines
            ADD CONSTRAINT ck_po_lines_qty_bounds CHECK (qty_received + qty_closed <= qty_ordered);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_po_lines_line_status'
    ) THEN
        ALTER TABLE po_lines
            ADD CONSTRAINT ck_po_lines_line_status CHECK (
                line_status IN ('OPEN', 'PARTIALLY_RECEIVED', 'RECEIVED', 'CLOSED')
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_po_lines_closed_reason'
    ) THEN
        ALTER TABLE po_lines
            ADD CONSTRAINT ck_po_lines_closed_reason CHECK (
                line_status <> 'CLOSED'
                OR (line_closed_reason IS NOT NULL AND length(btrim(line_closed_reason)) > 0)
            );
    END IF;
END $$;
