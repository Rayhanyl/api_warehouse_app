-- 012_add_barcode_to_items.sql
-- Purpose: Add optional unique barcode column to items table for USB/Bluetooth & Camera scanner support.

ALTER TABLE items ADD COLUMN IF NOT EXISTS barcode VARCHAR(64);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_items_barcode_not_blank'
    ) THEN
        ALTER TABLE items
            ADD CONSTRAINT ck_items_barcode_not_blank
            CHECK (barcode IS NULL OR length(btrim(barcode)) > 0);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_items_barcode_lower
    ON items (LOWER(barcode))
    WHERE barcode IS NOT NULL;
