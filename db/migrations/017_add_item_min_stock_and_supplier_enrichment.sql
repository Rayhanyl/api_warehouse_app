-- Tahap 37: Tambah min_stock pada items & pengayaan profil bank/pajak/fax pada suppliers

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS min_stock NUMERIC(18, 4) NOT NULL DEFAULT 0;

ALTER TABLE items
    DROP CONSTRAINT IF EXISTS ck_items_min_stock_nonneg;

ALTER TABLE items
    ADD CONSTRAINT ck_items_min_stock_nonneg CHECK (min_stock >= 0);

ALTER TABLE suppliers
    ADD COLUMN IF NOT EXISTS bank_name VARCHAR(120) NULL,
    ADD COLUMN IF NOT EXISTS bank_account_number VARCHAR(60) NULL,
    ADD COLUMN IF NOT EXISTS bank_account_holder VARCHAR(150) NULL,
    ADD COLUMN IF NOT EXISTS fax VARCHAR(50) NULL,
    ADD COLUMN IF NOT EXISTS npwp VARCHAR(40) NULL,
    ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(120) NULL,
    ADD COLUMN IF NOT EXISTS notes VARCHAR(500) NULL;
