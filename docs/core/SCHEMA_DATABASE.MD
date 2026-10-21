# Dokumen 2: Skema Database (PostgreSQL — Direct SQL / Tanpa ORM)

| | |
| --- | --- |
| **Versi** | 2.0 (selaras dengan `PRD.MD` v2.0 & `FOLDER_STRUCTURE.md`) |
| **Database** | PostgreSQL 13+ |
| **Akses Data** | Driver langsung (`psycopg` 3 + `ConnectionPool`), **tanpa ORM** |
| **Manajemen Skema** | Berkas migrasi `.sql` berurutan (*forward-only*) + tabel `schema_migrations` |

---

## 1. Prinsip Desain & Konvensi Skema

1. **Akses PostgreSQL Langsung & Migrasi SQL Murni (PRD 7.5):**
   * Aplikasi tidak menggunakan ORM (SQLAlchemy/Alembic). Seluruh perubahan skema dikelola melalui berkas SQL bernomor urut pada folder `db/migrations/` (`001_...sql` s.d. `008_...sql`) yang dijalankan oleh *runner* `db/migrate.py` dan dicatat pada tabel `schema_migrations`.
   * Database memisahkan **role pemilik skema** (`wms_owner`, digunakan saat migrasi) dan **role aplikasi** (`wms_app`, digunakan oleh layanan FastAPI sehari-hari).

2. **Konvensi Penamaan *Constraint* & Indeks Eksplisit (PRD 7.5):**
   * Primary Key: `pk_<tabel>`
   * Foreign Key: `fk_<tabel>_<kolom>`
   * Unique Constraint: `uq_<tabel>_<kolom>`
   * Check Constraint: `ck_<tabel>_<aturan>`
   * Index: `ix_<tabel>_<kolom>`

3. **Tipe Kunci Utama (*Primary Key*):**
   * Seluruh tabel yang memiliki kunci tunggal menggunakan `BIGINT GENERATED ALWAYS AS IDENTITY` (PRD 7.5) demi efisiensi indeks B-Tree, pengurutan penguncian baris (*lock ordering* pada PRD 6.5), dan kesederhanaan serialisasi JSON.
   * Tabel penghubung/komposit (`role_permissions`, `user_warehouses`, `document_sequences`) dan `schema_migrations` menggunakan kunci utama alami/komposit.

4. **Presisi Numerik & Zona Waktu (PRD 6.9, 7.4, 7.5):**
   * Seluruh kuantitas barang disimpan sebagai `NUMERIC(18, 4)` (tidak pernah menggunakan `FLOAT`/`REAL`).
   * Seluruh kolom waktu menggunakan `TIMESTAMPTZ` (`TIMESTAMP WITH TIME ZONE`) dalam standar UTC.

5. **Kolom Audit Umum (PRD Lampiran A):**
   * Seluruh tabel master dan transaksi memiliki kolom audit `created_at`, `updated_at`, dan `created_by` (kecuali tabel *append-only* `stock_movements` dan `audit_logs` yang tidak memiliki `updated_at` dan tidak pernah diubah).

---

## 2. Peta Pemetaan Berkas Migrasi

Sesuai arsitektur pada `FOLDER_STRUCTURE.md`, definisi DDL dibagi ke dalam berkas berikut:

| Berkas | Cakupan Tabel / Objek Database |
| --- | --- |
| `db/init/001_create_app_role.sql` | Pembuatan role `wms_app` (bukan *superuser*, bukan pemilik tabel). |
| `db/migrations/001_create_auth_tables.sql` | `roles`, `permissions`, `role_permissions`, `users`, `refresh_tokens` (+ `schema_migrations` dibuat oleh *runner*). |
| `db/migrations/002_create_master_tables.sql` | `categories`, `uoms`, `suppliers`, `items`, `warehouses`, `user_warehouses`, `storage_locations`. |
| `db/migrations/003_create_inventory_tables.sql` | `inventory_balances`, `stock_movements`. |
| `db/migrations/004_create_purchasing_tables.sql` | `purchase_orders`, `po_lines`, `goods_receipts`, `gr_lines`. |
| `db/migrations/005_create_transfer_opname.sql` | `stock_transfers`, `stock_transfer_lines`, `stock_opnames`, `stock_opname_lines`. |
| `db/migrations/006_create_audit_sequences.sql` | `audit_logs`, `document_sequences`. |
| `db/migrations/007_append_only_guards.sql` | Fungsi & *trigger* penolak `UPDATE`/`DELETE` pada `stock_movements` & `audit_logs`, serta `GRANT`/`REVOKE` untuk `wms_app` (AC-08). |
| `db/migrations/008_seed_roles_permissions.sql` | Data awal 5 peran dan 24 kode *permission* beserta pemetaannya sesuai Matriks 3.1 PRD. |

---

## 3. Peta Relasi Antar-Tabel (*Entity Relationship Summary*)

| Tabel Induk (*Parent*) | Tabel Anak (*Child*) | Kardinalitas | Aturan `ON DELETE` | Penjelasan Relasi |
| --- | --- | --- | --- | --- |
| `roles` | `role_permissions` | 1 : N | `CASCADE` | Pemetaan izin pada setiap peran. |
| `permissions` | `role_permissions` | 1 : N | `CASCADE` | Pemetaan izin ke peran (Many-to-Many). |
| `roles` | `users` | 1 : N | `RESTRICT` | Peran yang dipakai pengguna tidak boleh dihapus. |
| `users` | `user_warehouses` | 1 : N | `CASCADE` | Penugasan gudang untuk *Warehouse Scoping* (PRD 3.2). |
| `warehouses` | `user_warehouses` | 1 : N | `CASCADE` | Gudang yang ditugaskan kepada pengguna. |
| `users` | `refresh_tokens` | 1 : N | `CASCADE` | Sesi *Refresh Token* milik pengguna. |
| `refresh_tokens` | `refresh_tokens` | 1 : 1 | `SET NULL` | Pelacakan rotasi token melalui `replaced_by_id` (FR-01, AC-11). |
| `categories` | `items` | 1 : N | `RESTRICT` | Kategori barang. |
| `uoms` | `items` | 1 : N | `RESTRICT` | Satuan ukur dasar untuk setiap barang (FR-02). |
| `warehouses` | `storage_locations` | 1 : N | `RESTRICT` | Satu gudang memiliki banyak lokasi/rak penyimpanan (*bin*). |
| `warehouses`, `storage_locations`, `items` | `inventory_balances` | 1 : N | `RESTRICT` | Saldo stok aktual per `(warehouse_id, location_id, item_id)` dengan *composite FK*. |
| `warehouses`, `storage_locations`, `items` | `stock_movements` | 1 : N | `RESTRICT` | Buku besar mutasi stok (*append-only*) dengan *composite FK*. |
| `suppliers`, `warehouses` | `purchase_orders` | 1 : N | `RESTRICT` | Pesanan pembelian ke pemasok dengan gudang tujuan (`warehouse_id`). |
| `purchase_orders` | `po_lines` | 1 : N | `CASCADE` | Baris barang yang dipesan pada PO; 1 barang maks 1 baris per PO. |
| `purchase_orders` | `goods_receipts` | 1 : N | `RESTRICT` | Satu PO dapat memiliki beberapa dokumen GR (penerimaan parsial). |
| `goods_receipts` | `gr_lines` | 1 : N | `CASCADE` | Baris penerimaan barang terkait dengan header GR. |
| `po_lines` | `gr_lines` | 1 : N | `RESTRICT` | Setiap baris GR wajib mengacu pada baris PO (`po_line_id`) pada PO yang sama. |
| `warehouses`, `storage_locations` | `stock_transfers` | 1 : N | `RESTRICT` | Header transfer menyimpan gudang & lokasi asal serta gudang & lokasi tujuan (FR-06). |
| `stock_transfers` | `stock_transfer_lines` | 1 : N | `CASCADE` | Baris barang yang ditransfer beserta `qty`, `qty_received`, dan `variance_reason`. |
| `warehouses`, `storage_locations` | `stock_opnames` | 1 : N | `RESTRICT` | Sesi Opname mencakup satu gudang dan opsional satu lokasi (`location_id`). |
| `stock_opnames` | `stock_opname_lines` | 1 : N | `CASCADE` | Baris hitung fisik per lokasi & barang (`qty_system`, `qty_physical`, `qty_variance`). |

---

## 4. Spesifikasi Detail Tabel (Sesuai Lampiran A PRD)

### 4.1. Domain Autentikasi & Otorisasi (RBAC) — `001_create_auth_tables.sql`

* **`roles`**: Daftar peran pengguna (`id`, `name` unik, `description`, `created_at`, `updated_at`). Diisi awal 5 peran: `Super Admin`, `Warehouse Manager`, `Purchasing Staff`, `Warehouse Staff`, `Auditor`.
* **`permissions`**: Daftar kode izin sesuai Matriks 3.1 PRD (`id`, `code` unik mis. `po:issue`, `description`, `created_at`, `updated_at`).
* **`role_permissions`**: Pemetaan peran ke izin (`role_id`, `permission_id`, `created_at`).
* **`users`**: Akun pengguna (`id`, `username` unik, `email` unik, `password_hash`, `full_name`, `role_id`, `is_active`, `failed_login_count`, `locked_until`, `last_login_at`, `created_by`, `created_at`, `updated_at`). Kolom `failed_login_count` dan `locked_until` mendukung penguncian akun 15 menit setelah 5 kali gagal login berturut-turut (FR-01).
* **`refresh_tokens`**: Menyimpan *hash* *Refresh Token* (`id`, `user_id`, `token_hash` unik, `expires_at`, `revoked_at`, `replaced_by_id`, `created_at`). Mendukung rotasi token dan deteksi penggunaan ulang token yang sudah dicabut (FR-01, AC-11).

### 4.2. Domain Master Data & Penugasan Gudang — `002_create_master_tables.sql`

* **`categories`**: Kategori barang (`id`, `name` unik, `description`, `is_active`, `created_by`, `created_at`, `updated_at`).
* **`uoms`**: Satuan ukur dasar barang (`id`, `code` unik, `name`, `allow_decimal`, `is_active`, `created_by`, `created_at`, `updated_at`).
* **`suppliers`**: Data pemasok (`id`, `code` unik, `name`, `contact_person`, `phone`, `email`, `address`, `is_active`, `created_by`, `created_at`, `updated_at`).
* **`items`**: Data barang (`id`, `sku` unik, `name`, `description`, `category_id`, `uom_id`, `is_active`, `created_by`, `created_at`, `updated_at`).
* **`warehouses`**: Data gudang (`id`, `code` unik, `name`, `address`, `allow_negative_stock`, `is_active`, `created_by`, `created_at`, `updated_at`).
* **`user_warehouses`**: Penugasan pengguna ke gudang untuk *Warehouse Scoping* (`user_id`, `warehouse_id`, `created_by`, `created_at`).
* **`storage_locations`**: Lokasi penyimpanan di dalam gudang (`id`, `warehouse_id`, `code` unik per gudang, `name`, `is_active`, `created_by`, `created_at`, `updated_at`). Memiliki `UNIQUE (id, warehouse_id)` sebagai target *Composite Foreign Key*.

### 4.3. Domain Persediaan & Buku Besar (*Inventory & Ledger*) — `003_create_inventory_tables.sql`

* **`inventory_balances`**: Saldo stok aktual per `(warehouse_id, location_id, item_id)` (`id`, `warehouse_id`, `location_id`, `item_id`, `qty_on_hand NUMERIC(18,4)`, `created_by`, `created_at`, `updated_at`).
  * **Catatan Penting (PRD 6.1):** Tidak dipasang `CHECK (qty_on_hand >= 0)` pada tabel ini karena pengaturan `allow_negative_stock` berlaku per gudang dan divalidasi di lapisan aplikasi (`inventory_service.apply_movement`) setelah baris dikunci dengan `SELECT ... FOR UPDATE`.
* **`stock_movements`**: Buku besar pergerakan stok yang bersifat *append-only* (`id`, `movement_type`, `warehouse_id`, `location_id`, `item_id`, `qty_before`, `qty_change`, `qty_after`, `reference_type`, `reference_id`, `notes`, `created_by`, `created_at`).

### 4.4. Domain Pembelian & Penerimaan Barang — `004_create_purchasing_tables.sql`

* **`purchase_orders`**: Header PO (`id`, `po_number` unik, `supplier_id`, `warehouse_id` tujuan, `status`, `order_date`, `notes`, `issued_at`, `issued_by`, `closed_reason`, `closed_at`, `closed_by`, `created_by`, `created_at`, `updated_at`).
* **`po_lines`**: Baris PO (`id`, `po_id`, `item_id`, `qty_ordered`, `qty_received`, `notes`, `created_by`, `created_at`, `updated_at`). Memiliki `UNIQUE (po_id, item_id)` dan `CHECK (0 <= qty_received AND qty_received <= qty_ordered)`.
* **`goods_receipts`**: Header GR (`id`, `gr_number` unik, `po_id`, `warehouse_id`, `status`, `received_date`, `notes`, `posted_at`, `posted_by`, `created_by`, `created_at`, `updated_at`). Memiliki *Composite FK* `(po_id, warehouse_id)` ke `purchase_orders (id, warehouse_id)` sehingga gudang tujuan GR dijamin sama dengan gudang tujuan PO (FR-05).
* **`gr_lines`**: Baris GR (`id`, `gr_id`, `po_id`, `warehouse_id`, `po_line_id`, `location_id`, `qty_received`, `notes`, `created_by`, `created_at`, `updated_at`).

### 4.5. Domain Transfer Stok & Stock Opname — `005_create_transfer_opname.sql`

* **`stock_transfers`**: Header Transfer Stok (`id`, `transfer_number` unik, `source_warehouse_id`, `source_location_id`, `destination_warehouse_id`, `destination_location_id`, `status`, `notes`, `approved_by`, `approved_at`, `shipped_by`, `shipped_at`, `received_by`, `received_at`, `created_by`, `created_at`, `updated_at`).
  * Mendukung transfer antar-gudang maupun antar-lokasi di gudang yang sama, dengan syarat `(source_warehouse_id, source_location_id) <> (destination_warehouse_id, destination_location_id)` (FR-06, PRD 6.3).
* **`stock_transfer_lines`**: Baris Transfer Stok (`id`, `transfer_id`, `item_id`, `qty`, `qty_received`, `variance_reason`, `created_by`, `created_at`, `updated_at`).
* **`stock_opnames`**: Header Stock Opname (`id`, `opname_number` unik, `warehouse_id`, `location_id` opsional, `status`, `notes`, `started_at`, `started_by`, `submitted_at`, `submitted_by`, `approved_by`, `approved_at`, `rejection_reason`, `created_by`, `created_at`, `updated_at`).
* **`stock_opname_lines`**: Baris Stock Opname (`id`, `opname_id`, `warehouse_id`, `location_id`, `item_id`, `qty_system`, `qty_physical`, `qty_variance`, `counted_by`, `counted_at`, `notes`, `created_by`, `created_at`, `updated_at`).

### 4.6. Domain Audit Log, Penomoran Dokumen & Migrasi — `006_create_audit_sequences.sql`

* **`audit_logs`**: Jejak audit *append-only* (`id`, `user_id` opsional untuk gagal login tak dikenal, `action`, `entity_type`, `entity_id`, `old_values JSONB`, `new_values JSONB`, `ip_address`, `created_at`).
* **`document_sequences`**: Penomoran dokumen atomik per jenis dokumen dan periode `YYYYMM` (`doc_type`, `period`, `last_value`, `updated_at`) untuk format `{PREFIX}-{YYYYMM}-{NNNN}` (FR-10).
* **`schema_migrations`**: Pencatat berkas migrasi yang telah diterapkan (`version`, `applied_at`).

---

## 5. Definisi Skema DDL PostgreSQL Lengkap

### 5.0. Inisialisasi Role Aplikasi (`db/init/001_create_app_role.sql`)

```sql
-- Dijalankan sekali saat inisialisasi cluster/database oleh superuser/owner
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wms_app') THEN
        CREATE ROLE wms_app WITH LOGIN PASSWORD 'ganti_di_env_produksi' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;
```

### 5.1. Tabel Pelacak Migrasi (Dibuat otomatis oleh `db/migrate.py`)

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(100) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_schema_migrations PRIMARY KEY (version)
);
```

### 5.2. `001_create_auth_tables.sql` — Autentikasi & RBAC

```sql
-- ============================================================================
-- 001: DOMAIN AUTENTIKASI & OTORISASI (RBAC)
-- ============================================================================

CREATE TABLE roles (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_roles PRIMARY KEY (id),
    CONSTRAINT uq_roles_name UNIQUE (name)
);

CREATE TABLE permissions (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    code VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_permissions PRIMARY KEY (id),
    CONSTRAINT uq_permissions_code UNIQUE (code)
);

CREATE TABLE role_permissions (
    role_id BIGINT NOT NULL,
    permission_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_role_permissions_role_id
        FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permissions_permission_id
        FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

CREATE INDEX ix_role_permissions_permission_id ON role_permissions (permission_id);

CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    username VARCHAR(64) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role_id BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT fk_users_role_id
        FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE RESTRICT,
    CONSTRAINT fk_users_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_users_failed_login_non_negative
        CHECK (failed_login_count >= 0)
);

CREATE INDEX ix_users_role_id ON users (role_id);
CREATE INDEX ix_users_is_active ON users (is_active);

CREATE TABLE refresh_tokens (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id BIGINT NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    replaced_by_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_refresh_tokens PRIMARY KEY (id),
    CONSTRAINT uq_refresh_tokens_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_refresh_tokens_user_id
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_refresh_tokens_replaced_by_id
        FOREIGN KEY (replaced_by_id) REFERENCES refresh_tokens (id) ON DELETE SET NULL
);

CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX ix_refresh_tokens_expires_at ON refresh_tokens (expires_at);
```

### 5.3. `002_create_master_tables.sql` — Master Data, Gudang & Lokasi

```sql
-- ============================================================================
-- 002: DOMAIN MASTER DATA & MULTI-GUDANG
-- ============================================================================

CREATE TABLE categories (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_categories PRIMARY KEY (id),
    CONSTRAINT uq_categories_name UNIQUE (name),
    CONSTRAINT fk_categories_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_categories_is_active ON categories (is_active);

CREATE TABLE uoms (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(60) NOT NULL,
    allow_decimal BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_uoms PRIMARY KEY (id),
    CONSTRAINT uq_uoms_code UNIQUE (code),
    CONSTRAINT fk_uoms_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_uoms_is_active ON uoms (is_active);

CREATE TABLE suppliers (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(150) NOT NULL,
    contact_person VARCHAR(120),
    phone VARCHAR(30),
    email VARCHAR(255),
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_suppliers PRIMARY KEY (id),
    CONSTRAINT uq_suppliers_code UNIQUE (code),
    CONSTRAINT fk_suppliers_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_suppliers_name ON suppliers (name);
CREATE INDEX ix_suppliers_is_active ON suppliers (is_active);

CREATE TABLE items (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    sku VARCHAR(64) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category_id BIGINT NOT NULL,
    uom_id BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_items PRIMARY KEY (id),
    CONSTRAINT uq_items_sku UNIQUE (sku),
    CONSTRAINT fk_items_category_id
        FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE RESTRICT,
    CONSTRAINT fk_items_uom_id
        FOREIGN KEY (uom_id) REFERENCES uoms (id) ON DELETE RESTRICT,
    CONSTRAINT fk_items_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_items_name ON items (name);
CREATE INDEX ix_items_category_id ON items (category_id);
CREATE INDEX ix_items_uom_id ON items (uom_id);
CREATE INDEX ix_items_is_active ON items (is_active);

CREATE TABLE warehouses (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(150) NOT NULL,
    address TEXT,
    allow_negative_stock BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_warehouses PRIMARY KEY (id),
    CONSTRAINT uq_warehouses_code UNIQUE (code),
    CONSTRAINT fk_warehouses_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_warehouses_is_active ON warehouses (is_active);

CREATE TABLE user_warehouses (
    user_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_warehouses PRIMARY KEY (user_id, warehouse_id),
    CONSTRAINT fk_user_warehouses_user_id
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_warehouses_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_warehouses_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_user_warehouses_warehouse_id ON user_warehouses (warehouse_id);

CREATE TABLE storage_locations (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    warehouse_id BIGINT NOT NULL,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(120) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_storage_locations PRIMARY KEY (id),
    CONSTRAINT uq_storage_locations_warehouse_code UNIQUE (warehouse_id, code),
    CONSTRAINT uq_storage_locations_id_warehouse UNIQUE (id, warehouse_id),
    CONSTRAINT fk_storage_locations_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_storage_locations_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_storage_locations_warehouse_id ON storage_locations (warehouse_id);
CREATE INDEX ix_storage_locations_is_active ON storage_locations (is_active);
```

### 5.4. `003_create_inventory_tables.sql` — Saldo Stok & Buku Besar

```sql
-- ============================================================================
-- 003: DOMAIN PERSEDIAAN & BUKU BESAR (INVENTORY & LEDGER)
-- ============================================================================

CREATE TABLE inventory_balances (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty_on_hand NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_inventory_balances PRIMARY KEY (id),
    CONSTRAINT uq_inventory_balances_wh_loc_item
        UNIQUE (warehouse_id, location_id, item_id),
    CONSTRAINT fk_inventory_balances_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_inventory_balances_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_inventory_balances_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_inventory_balances_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT
    -- Catatan PRD 6.1: TIDAK dipasang CHECK (qty_on_hand >= 0) karena aturan
    -- allow_negative_stock berlaku per gudang dan ditegakkan di aplikasi di bawah FOR UPDATE.
);

CREATE INDEX ix_inventory_balances_item_id ON inventory_balances (item_id);
CREATE INDEX ix_inventory_balances_warehouse_item ON inventory_balances (warehouse_id, item_id);

CREATE TABLE stock_movements (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    movement_type VARCHAR(30) NOT NULL,
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty_before NUMERIC(18, 4) NOT NULL,
    qty_change NUMERIC(18, 4) NOT NULL,
    qty_after NUMERIC(18, 4) NOT NULL,
    reference_type VARCHAR(30) NOT NULL,
    reference_id BIGINT NOT NULL,
    notes TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_movements PRIMARY KEY (id),
    CONSTRAINT fk_stock_movements_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movements_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movements_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movements_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_movements_movement_type CHECK (
        movement_type IN (
            'IN_PURCHASE',
            'OUT_TRANSFER',
            'IN_TRANSFER',
            'ADJUSTMENT_PLUS',
            'ADJUSTMENT_MINUS'
        )
    ),
    CONSTRAINT ck_stock_movements_reference_type CHECK (
        reference_type IN (
            'GOODS_RECEIPT',
            'STOCK_TRANSFER',
            'STOCK_OPNAME'
        )
    ),
    CONSTRAINT ck_stock_movements_qty_change_non_zero
        CHECK (qty_change <> 0),
    CONSTRAINT ck_stock_movements_balance_math
        CHECK (qty_after = qty_before + qty_change),
    CONSTRAINT ck_stock_movements_direction_sign CHECK (
        (movement_type IN ('IN_PURCHASE', 'IN_TRANSFER', 'ADJUSTMENT_PLUS') AND qty_change > 0)
        OR
        (movement_type IN ('OUT_TRANSFER', 'ADJUSTMENT_MINUS') AND qty_change < 0)
    ),
    CONSTRAINT ck_stock_movements_type_ref_match CHECK (
        (movement_type = 'IN_PURCHASE' AND reference_type = 'GOODS_RECEIPT')
        OR
        (movement_type IN ('OUT_TRANSFER', 'IN_TRANSFER') AND reference_type = 'STOCK_TRANSFER')
        OR
        (movement_type IN ('ADJUSTMENT_PLUS', 'ADJUSTMENT_MINUS') AND reference_type = 'STOCK_OPNAME')
    )
);

CREATE INDEX ix_stock_movements_wh_item_created
    ON stock_movements (warehouse_id, item_id, created_at DESC);
CREATE INDEX ix_stock_movements_wh_loc_item_id
    ON stock_movements (warehouse_id, location_id, item_id, id DESC);
CREATE INDEX ix_stock_movements_reference
    ON stock_movements (reference_type, reference_id);
CREATE INDEX ix_stock_movements_created_at
    ON stock_movements (created_at DESC);
```

### 5.5. `004_create_purchasing_tables.sql` — Purchase Order & Goods Receipt

```sql
-- ============================================================================
-- 004: DOMAIN PURCHASE ORDER (PO) & GOODS RECEIPT (GR)
-- ============================================================================

CREATE TABLE purchase_orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    po_number VARCHAR(50) NOT NULL,
    supplier_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    order_date DATE NOT NULL,
    notes TEXT,
    issued_at TIMESTAMPTZ,
    issued_by BIGINT,
    closed_reason TEXT,
    closed_at TIMESTAMPTZ,
    closed_by BIGINT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_purchase_orders PRIMARY KEY (id),
    CONSTRAINT uq_purchase_orders_po_number UNIQUE (po_number),
    CONSTRAINT uq_purchase_orders_id_warehouse UNIQUE (id, warehouse_id),
    CONSTRAINT fk_purchase_orders_supplier_id
        FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_issued_by
        FOREIGN KEY (issued_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_closed_by
        FOREIGN KEY (closed_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_orders_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_purchase_orders_status CHECK (
        status IN (
            'DRAFT',
            'ISSUED',
            'PARTIALLY_RECEIVED',
            'RECEIVED',
            'CLOSED',
            'CANCELLED'
        )
    ),
    CONSTRAINT ck_purchase_orders_closed_reason CHECK (
        status <> 'CLOSED' OR (closed_reason IS NOT NULL AND length(btrim(closed_reason)) > 0)
    )
);

CREATE INDEX ix_purchase_orders_supplier_id ON purchase_orders (supplier_id);
CREATE INDEX ix_purchase_orders_warehouse_id ON purchase_orders (warehouse_id);
CREATE INDEX ix_purchase_orders_status ON purchase_orders (status);
CREATE INDEX ix_purchase_orders_order_date ON purchase_orders (order_date DESC);

CREATE TABLE po_lines (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    po_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty_ordered NUMERIC(18, 4) NOT NULL,
    qty_received NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    notes TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_po_lines PRIMARY KEY (id),
    CONSTRAINT uq_po_lines_po_item UNIQUE (po_id, item_id),
    CONSTRAINT uq_po_lines_id_po UNIQUE (id, po_id),
    CONSTRAINT fk_po_lines_po_id
        FOREIGN KEY (po_id) REFERENCES purchase_orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_po_lines_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_po_lines_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_po_lines_qty_ordered_positive
        CHECK (qty_ordered > 0),
    CONSTRAINT ck_po_lines_qty_received_bounds
        CHECK (0 <= qty_received AND qty_received <= qty_ordered)
);

CREATE INDEX ix_po_lines_po_id ON po_lines (po_id);
CREATE INDEX ix_po_lines_item_id ON po_lines (item_id);

CREATE TABLE goods_receipts (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    gr_number VARCHAR(50) NOT NULL,
    po_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    received_date DATE NOT NULL,
    notes TEXT,
    posted_at TIMESTAMPTZ,
    posted_by BIGINT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_goods_receipts PRIMARY KEY (id),
    CONSTRAINT uq_goods_receipts_gr_number UNIQUE (gr_number),
    CONSTRAINT uq_goods_receipts_id_po_wh UNIQUE (id, po_id, warehouse_id),
    CONSTRAINT fk_goods_receipts_po_warehouse
        FOREIGN KEY (po_id, warehouse_id)
        REFERENCES purchase_orders (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_goods_receipts_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_goods_receipts_posted_by
        FOREIGN KEY (posted_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_goods_receipts_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_goods_receipts_status CHECK (
        status IN ('DRAFT', 'POSTED', 'CANCELLED')
    )
);

CREATE INDEX ix_goods_receipts_po_id ON goods_receipts (po_id);
CREATE INDEX ix_goods_receipts_warehouse_id ON goods_receipts (warehouse_id);
CREATE INDEX ix_goods_receipts_status ON goods_receipts (status);

CREATE TABLE gr_lines (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    gr_id BIGINT NOT NULL,
    po_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    po_line_id BIGINT NOT NULL,
    location_id BIGINT NOT NULL,
    qty_received NUMERIC(18, 4) NOT NULL,
    notes TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_gr_lines PRIMARY KEY (id),
    CONSTRAINT uq_gr_lines_gr_po_line_loc
        UNIQUE (gr_id, po_line_id, location_id),
    CONSTRAINT fk_gr_lines_gr_header
        FOREIGN KEY (gr_id, po_id, warehouse_id)
        REFERENCES goods_receipts (id, po_id, warehouse_id) ON DELETE CASCADE,
    CONSTRAINT fk_gr_lines_po_line
        FOREIGN KEY (po_line_id, po_id)
        REFERENCES po_lines (id, po_id) ON DELETE RESTRICT,
    CONSTRAINT fk_gr_lines_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_gr_lines_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_gr_lines_qty_positive
        CHECK (qty_received > 0)
);

CREATE INDEX ix_gr_lines_gr_id ON gr_lines (gr_id);
CREATE INDEX ix_gr_lines_po_line_id ON gr_lines (po_line_id);
CREATE INDEX ix_gr_lines_location_id ON gr_lines (location_id);
```

### 5.6. `005_create_transfer_opname.sql` — Transfer Stok & Stock Opname

```sql
-- ============================================================================
-- 005: DOMAIN TRANSFER STOK & STOCK OPNAME
-- ============================================================================

CREATE TABLE stock_transfers (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    transfer_number VARCHAR(50) NOT NULL,
    source_warehouse_id BIGINT NOT NULL,
    source_location_id BIGINT NOT NULL,
    destination_warehouse_id BIGINT NOT NULL,
    destination_location_id BIGINT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    notes TEXT,
    approved_by BIGINT,
    approved_at TIMESTAMPTZ,
    shipped_by BIGINT,
    shipped_at TIMESTAMPTZ,
    received_by BIGINT,
    received_at TIMESTAMPTZ,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_transfers PRIMARY KEY (id),
    CONSTRAINT uq_stock_transfers_transfer_number UNIQUE (transfer_number),
    CONSTRAINT fk_stock_transfers_source_warehouse_id
        FOREIGN KEY (source_warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_source_location_warehouse
        FOREIGN KEY (source_location_id, source_warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_destination_warehouse_id
        FOREIGN KEY (destination_warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_destination_location_warehouse
        FOREIGN KEY (destination_location_id, destination_warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_approved_by
        FOREIGN KEY (approved_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_shipped_by
        FOREIGN KEY (shipped_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_received_by
        FOREIGN KEY (received_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfers_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_transfers_status CHECK (
        status IN ('DRAFT', 'APPROVED', 'SHIPPED', 'RECEIVED', 'CANCELLED')
    ),
    -- PRD 6.3: Kombinasi (source_warehouse_id, source_location_id) <> (destination_warehouse_id, destination_location_id)
    CONSTRAINT ck_stock_transfers_different_src_dst CHECK (
        source_warehouse_id <> destination_warehouse_id
        OR source_location_id <> destination_location_id
    )
);

CREATE INDEX ix_stock_transfers_source_wh ON stock_transfers (source_warehouse_id);
CREATE INDEX ix_stock_transfers_dest_wh ON stock_transfers (destination_warehouse_id);
CREATE INDEX ix_stock_transfers_status ON stock_transfers (status);

CREATE TABLE stock_transfer_lines (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    transfer_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty NUMERIC(18, 4) NOT NULL,
    qty_received NUMERIC(18, 4),
    variance_reason TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_transfer_lines PRIMARY KEY (id),
    CONSTRAINT uq_stock_transfer_lines_transfer_item
        UNIQUE (transfer_id, item_id),
    CONSTRAINT fk_stock_transfer_lines_transfer_id
        FOREIGN KEY (transfer_id) REFERENCES stock_transfers (id) ON DELETE CASCADE,
    CONSTRAINT fk_stock_transfer_lines_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_transfer_lines_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_transfer_lines_qty_positive
        CHECK (qty > 0),
    CONSTRAINT ck_stock_transfer_lines_qty_received_bounds
        CHECK (qty_received IS NULL OR (0 <= qty_received AND qty_received <= qty)),
    -- PRD 6.7: Jika qty_received < qty, variance_reason wajib diisi
    CONSTRAINT ck_stock_transfer_lines_variance_reason CHECK (
        qty_received IS NULL
        OR qty_received = qty
        OR (variance_reason IS NOT NULL AND length(btrim(variance_reason)) > 0)
    )
);

CREATE INDEX ix_stock_transfer_lines_transfer_id ON stock_transfer_lines (transfer_id);
CREATE INDEX ix_stock_transfer_lines_item_id ON stock_transfer_lines (item_id);

CREATE TABLE stock_opnames (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    opname_number VARCHAR(50) NOT NULL,
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    notes TEXT,
    started_at TIMESTAMPTZ,
    started_by BIGINT,
    submitted_at TIMESTAMPTZ,
    submitted_by BIGINT,
    approved_by BIGINT,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_opnames PRIMARY KEY (id),
    CONSTRAINT uq_stock_opnames_opname_number UNIQUE (opname_number),
    CONSTRAINT uq_stock_opnames_id_warehouse UNIQUE (id, warehouse_id),
    CONSTRAINT fk_stock_opnames_warehouse_id
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id) ON DELETE RESTRICT,
    -- MATCH SIMPLE (default PG): bila location_id NULL (opname 1 gudang penuh), FK dilewati;
    -- bila location_id diisi, wajib milik warehouse_id tersebut.
    CONSTRAINT fk_stock_opnames_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opnames_started_by
        FOREIGN KEY (started_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opnames_submitted_by
        FOREIGN KEY (submitted_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opnames_approved_by
        FOREIGN KEY (approved_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opnames_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_opnames_status CHECK (
        status IN (
            'DRAFT',
            'IN_PROGRESS',
            'WAITING_APPROVAL',
            'COMPLETED',
            'CANCELLED'
        )
    )
);

CREATE INDEX ix_stock_opnames_warehouse_id ON stock_opnames (warehouse_id);
CREATE INDEX ix_stock_opnames_location_id ON stock_opnames (location_id);
CREATE INDEX ix_stock_opnames_status ON stock_opnames (status);

-- Indeks parsial untuk mempercepat pemeriksaan pembekuan lokasi (PRD 6.6 & FR-07)
CREATE INDEX ix_stock_opnames_active_scope
    ON stock_opnames (warehouse_id, location_id)
    WHERE status IN ('IN_PROGRESS', 'WAITING_APPROVAL');

CREATE TABLE stock_opname_lines (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    opname_id BIGINT NOT NULL,
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT NOT NULL,
    item_id BIGINT NOT NULL,
    qty_system NUMERIC(18, 4) NOT NULL,
    qty_physical NUMERIC(18, 4),
    qty_variance NUMERIC(18, 4) GENERATED ALWAYS AS (qty_physical - qty_system) STORED,
    counted_by BIGINT,
    counted_at TIMESTAMPTZ,
    notes TEXT,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_opname_lines PRIMARY KEY (id),
    CONSTRAINT uq_stock_opname_lines_opname_loc_item
        UNIQUE (opname_id, location_id, item_id),
    CONSTRAINT fk_stock_opname_lines_header
        FOREIGN KEY (opname_id, warehouse_id)
        REFERENCES stock_opnames (id, warehouse_id) ON DELETE CASCADE,
    CONSTRAINT fk_stock_opname_lines_location_warehouse
        FOREIGN KEY (location_id, warehouse_id)
        REFERENCES storage_locations (id, warehouse_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opname_lines_item_id
        FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opname_lines_counted_by
        FOREIGN KEY (counted_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_opname_lines_created_by
        FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT ck_stock_opname_lines_qty_physical_non_negative
        CHECK (qty_physical IS NULL OR qty_physical >= 0)
);

CREATE INDEX ix_stock_opname_lines_opname_id ON stock_opname_lines (opname_id);
CREATE INDEX ix_stock_opname_lines_location_id ON stock_opname_lines (location_id);
```

### 5.7. `006_create_audit_sequences.sql` — Audit Log & Penomoran Dokumen

```sql
-- ============================================================================
-- 006: DOMAIN AUDIT LOG & PENOMORAN DOKUMEN (SEQUENCES)
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
```

### 5.8. `007_append_only_guards.sql` — Penegakan Imutabilitas & Hak Role `wms_app` (PRD 6.4, AC-08)

```sql
-- ============================================================================
-- 007: PENEGAKAN APPEND-ONLY (TRIGGER + HAK AKSES ROLE wms_app)
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

-- Pengaturan hak akses untuk role aplikasi (wms_app) bila role tersedia
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
```

### 5.9. `008_seed_roles_permissions.sql` — Seed Peran & Matriks Permission (PRD 3.1)

```sql
-- ============================================================================
-- 008: SEED 5 PERAN & 24 PERMISSION SESUAI MATRIKS 3.1 PRD
-- ============================================================================

INSERT INTO roles (name, description) VALUES
    ('Super Admin', 'Administrator sistem TI dengan akses penuh ke seluruh modul dan seluruh gudang'),
    ('Warehouse Manager', 'Kepala operasional gudang; menyetujui Transfer & Opname, menutup PO, memantau stok'),
    ('Purchasing Staff', 'Staf pengadaan/pembelian; mengelola master barang/pemasok dan siklus PO'),
    ('Warehouse Staff', 'Operator operasional gudang pada gudang yang ditugaskan (GR, Transfer, hitung Opname)'),
    ('Auditor', 'Pemeriksa internal / manajemen dengan akses baca ke seluruh modul dan Audit Log')
ON CONFLICT (name) DO NOTHING;

INSERT INTO permissions (code, description) VALUES
    ('user:manage',      'Kelola pengguna, role/permission, penugasan gudang'),
    ('warehouse:manage', 'Kelola gudang & konfigurasinya'),
    ('location:manage',  'Kelola lokasi penyimpanan'),
    ('master:manage',    'Kelola kategori, UoM, barang, pemasok'),
    ('master:read',      'Baca master data'),
    ('po:create',        'Buat/ubah PO DRAFT, batalkan PO DRAFT'),
    ('po:issue',         'Terbitkan PO'),
    ('po:cancel',        'Batalkan PO ISSUED'),
    ('po:close',         'Tutup PO'),
    ('po:read',          'Baca PO'),
    ('gr:manage',        'Buat, ubah, posting, batalkan GR'),
    ('gr:read',          'Baca GR'),
    ('transfer:create',  'Buat/ubah/batalkan Transfer DRAFT'),
    ('transfer:approve', 'Setujui / batalkan Transfer'),
    ('transfer:ship',    'Kirim Transfer (SHIPPED)'),
    ('transfer:receive', 'Terima Transfer (RECEIVED)'),
    ('transfer:read',    'Baca Transfer'),
    ('opname:manage',    'Buat, mulai, batalkan sesi Opname'),
    ('opname:count',     'Input hitung fisik & ajukan persetujuan'),
    ('opname:approve',   'Setujui / tolak hasil Opname'),
    ('opname:read',      'Baca Opname'),
    ('stock:read',       'Baca saldo stok'),
    ('ledger:read',      'Baca Stock Movement Ledger'),
    ('audit:read',       'Baca Audit Log')
ON CONFLICT (code) DO NOTHING;

-- 1. Super Admin: seluruh permission
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'Super Admin'
ON CONFLICT DO NOTHING;

-- 2. Warehouse Manager
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'location:manage',
    'master:read',
    'po:close',
    'po:read',
    'gr:read',
    'transfer:approve',
    'transfer:read',
    'opname:manage',
    'opname:approve',
    'opname:read',
    'stock:read',
    'ledger:read'
)
WHERE r.name = 'Warehouse Manager'
ON CONFLICT DO NOTHING;

-- 3. Purchasing Staff
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'master:manage',
    'master:read',
    'po:create',
    'po:issue',
    'po:cancel',
    'po:close',
    'po:read',
    'gr:read',
    'stock:read'
)
WHERE r.name = 'Purchasing Staff'
ON CONFLICT DO NOTHING;

-- 4. Warehouse Staff
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'master:read',
    'po:read',
    'gr:manage',
    'gr:read',
    'transfer:create',
    'transfer:ship',
    'transfer:receive',
    'transfer:read',
    'opname:count',
    'opname:read',
    'stock:read',
    'ledger:read'
)
WHERE r.name = 'Warehouse Staff'
ON CONFLICT DO NOTHING;

-- 5. Auditor
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'master:read',
    'po:read',
    'gr:read',
    'transfer:read',
    'opname:read',
    'stock:read',
    'ledger:read',
    'audit:read'
)
WHERE r.name = 'Auditor'
ON CONFLICT DO NOTHING;
```

---

## 6. Aturan Integritas Data & Pola Query Kunci

1. **Komposit Foreign Key untuk Integritas Lokasi & Gudang (PRD 6.3, 7.5):**
   * Tabel `storage_locations` memiliki `uq_storage_locations_id_warehouse UNIQUE (id, warehouse_id)`.
   * Tabel `inventory_balances`, `stock_movements`, `gr_lines`, `stock_transfers` (baik lokasi asal maupun tujuan), `stock_opnames`, dan `stock_opname_lines` menggunakan *Composite Foreign Key* `(location_id, warehouse_id)` yang mengarah ke `storage_locations (id, warehouse_id)`.
   * Mesin PostgreSQL menjamin mustahil sebuah dokumen di Gudang A merujuk atau memotong stok pada lokasi milik Gudang B.

2. **Integritas Relasi Penerimaan Barang terhadap PO (PRD FR-05):**
   * `goods_receipts` memiliki `fk_goods_receipts_po_warehouse FOREIGN KEY (po_id, warehouse_id) REFERENCES purchase_orders (id, warehouse_id)` yang menjamin GR hanya bisa dibuat pada gudang tujuan PO.
   * `gr_lines` memiliki `fk_gr_lines_po_line FOREIGN KEY (po_line_id, po_id) REFERENCES po_lines (id, po_id)` yang menjamin baris GR hanya dapat mengacu pada baris PO milik dokumen PO yang sama.

3. **Pencegahan Stok Negatif & Urutan Penguncian (PRD 6.1, 6.5):**
   * Aturan `allow_negative_stock` bersifat per gudang sehingga **tidak** menggunakan `CHECK (qty_on_hand >= 0)` pada tabel `inventory_balances`.
   * Seluruh perubahan stok wajib melalui `inventory_service.apply_movement` di dalam transaksi dengan urutan penguncian seragam:
     1. Baris *header* dokumen (`SELECT ... FOR UPDATE`).
     2. Baris PO terkait (`SELECT ... FOR UPDATE`), bila ada.
     3. Baris lokasi penyimpanan (`SELECT ... FROM storage_locations WHERE id = %s FOR SHARE`, atau `FOR UPDATE` saat memulai Opname) diurutkan berdasarkan `id`.
     4. *Upsert* baris saldo (`INSERT INTO inventory_balances ... VALUES (..., 0) ON CONFLICT (warehouse_id, location_id, item_id) DO NOTHING`) lalu kunci baris saldo (`SELECT qty_on_hand FROM inventory_balances WHERE warehouse_id = %s AND location_id = %s AND item_id = %s FOR UPDATE`) diurutkan berdasarkan `(warehouse_id, location_id, item_id)`.

4. **Penomoran Dokumen Aman Konkurensi (PRD FR-10):**
   * Saat membuat PO/GR/Transfer/Opname baru, `sequence_repo` mengeksekusi *upsert* atomik pada `document_sequences`:
     ```sql
     INSERT INTO document_sequences (doc_type, period, last_value, updated_at)
     VALUES (%s, %s, 1, CURRENT_TIMESTAMP)
     ON CONFLICT (doc_type, period)
     DO UPDATE SET
         last_value = document_sequences.last_value + 1,
         updated_at = CURRENT_TIMESTAMP
     RETURNING last_value;
     ```
   * Nilai `last_value` diformat menjadi `{PREFIX}-{YYYYMM}-{NNNN}` (contoh: `PO-202610-0001`).

5. **Imutabilitas Berlapis pada Buku Besar & Audit Log (PRD 6.4, AC-08):**
   * Lapisan 1 (*Database Trigger*): Trigger `BEFORE UPDATE OR DELETE` pada `stock_movements` dan `audit_logs` selalu menolak perubahan meskipun dijalankan oleh pemilik tabel.
   * Lapisan 2 (*Database Privileges*): Role koneksi aplikasi (`wms_app`) dicabut hak `UPDATE`, `DELETE`, dan `TRUNCATE`-nya pada kedua tabel tersebut.
