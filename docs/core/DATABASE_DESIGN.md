# Database Design & Schema Specification

Dokumen ini menerjemahkan [PRD General](PRD_GENERAL.md) dan kebutuhan teknis
[PRD Backend](PRD_BACKEND.md) ke rancangan persistence. DDL rinci dan
pemetaan migration yang sudah berjalan tetap tersedia pada
[SCHEMA_DATABASE](SCHEMA_DATABASE.MD); dokumen ini adalah peta desain dan
aturan integritas, bukan sumber business requirement baru.

## 1. Prinsip desain

- PostgreSQL 13+ dengan SQL langsung melalui `psycopg` 3/`psycopg_pool`.
- Migration bernomor, forward-only, dicatat pada `schema_migrations`.
- Primary key tunggal: `BIGINT GENERATED ALWAYS AS IDENTITY`; tabel penghubung
  menggunakan key alami/komposit.
- Waktu: `TIMESTAMPTZ`; kuantitas: `NUMERIC(18,4)`.
- Constraint dan index memiliki nama eksplisit (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`).
- Role migration/pemilik dipisahkan dari role aplikasi `wms_app`.

## 2. Entitas dan tabel

| Modul | Entitas/tabel | Feature / Requirement PRD General |
| --- | --- | --- |
| `PLT` | `document_sequences`, `schema_migrations` | `PLT-F01` (`FR-PLT-001`), `PLT-F05` (`FR-PLT-005`), `AC-15`, `AC-18` |
| `IAM` | `roles`, `permissions`, `role_permissions`, `users`, `user_warehouses`, `refresh_tokens`, `menus` | `IAM-F01..F09` (`FR-IAM-001..009`), `AC-05`, `AC-11`, `AC-12`, `AC-14` |
| `AUD` | `audit_logs` | `AUD-F01..F02` (`FR-AUD-001..002`), `AC-05`, `AC-07`, `AC-08`, `AC-22` |
| `MST` | `categories`, `uoms`, `suppliers`, `items` | `MST-F01..F07` (`FR-MST-001..007`), `AC-19`, `AC-30`, `AC-31` |
| `WHS` | `warehouses`, `storage_locations` | `WHS-F01..F03` (`FR-WHS-001..003`), `AC-20` |
| `INV` | `inventory_balances`, `stock_movements` | `INV-F01..F06` (`FR-INV-001..006`), `AC-02`, `AC-03`, `AC-06`, `AC-08`, `AC-13` |
| `PUR` | `purchase_orders`, `po_lines` | `PUR-F01..F04` (`FR-PUR-001..004`), `AC-01`, `AC-21` |
| `RCV` | `goods_receipts`, `gr_lines` | `RCV-F01..F04` (`FR-RCV-001..004`), `AC-01`, `AC-07`, `AC-13`, `AC-21` |
| `TRF` | `stock_transfers`, `stock_transfer_lines` | `TRF-F01..F05` (`FR-TRF-001..005`), `AC-02`, `AC-03`, `AC-06`, `AC-09`, `AC-21` |
| `OPN` | `stock_opnames`, `stock_opname_lines` | `OPN-F01..F06` (`FR-OPN-001..006`), `AC-04`, `AC-10`, `AC-21` |
| `TNT` *(Fase 2 — M9)* | `tenants`, `plans`, `platform_admins`, `platform_refresh_tokens` | `TNT-F01..F06` (`FR-TNT-001..006`), `AC-23`, `AC-24`, `AC-25`, `AC-27`, `AC-28`, `AC-29` |
| `CFG` *(Fase 2 — M9)* | `settings` | `CFG-F01..F04` (`FR-CFG-001..004`), `AC-26` |

Kolom, nullable, default, foreign key, dan DDL normatif per tabel harus
diubah pada [SCHEMA_DATABASE](SCHEMA_DATABASE.MD) dan migration terkait,
bukan diduplikasi di dokumen layer.

## 3. Relasi dan integritas

- Role memiliki banyak user dan permission melalui tabel penghubung.
- User memiliki penugasan gudang melalui `user_warehouses`.
- Warehouse memiliki banyak storage location; saldo dan movement mengacu pada
  kombinasi warehouse-location-item yang konsisten.
- PO memiliki banyak PO line dan dapat memiliki banyak GR; GR line mengacu pada
  PO line dalam PO yang sama.
- Transfer dan opname memiliki header serta line dengan foreign key cascade
  sesuai schema aktual.
- Menu memiliki hierarki self-reference dan permission opsional.
- Master yang dipakai transaksi tidak boleh dihapus/disable bila melanggar
  aturan `ENTITY_IN_USE`.

## 4. Data integrity dan append-only

`stock_movements` dan `audit_logs` append-only. Trigger, privilege, dan service
bersama-sama mencegah update/delete aplikasi. Saldo tidak boleh berubah tanpa
movement. Validasi stok negatif, over-receipt, lokasi frozen, dan concurrency
dilakukan dalam transaksi setelah row yang relevan dikunci; jangan menggantinya
dengan `CHECK (qty_on_hand >= 0)` karena aturan bergantung pada gudang.

## 5. Migration map

| Migration | Cakupan |
| --- | --- |
| `001` | Auth dan RBAC |
| `002` | Master data, warehouse, assignment, location |
| `003` | Inventory balance dan stock movement |
| `004` | PO dan goods receipt |
| `005` | Transfer dan opname |
| `006` | Audit log dan document sequence |
| `007` | Append-only guard dan privilege |
| `008` | Seed role dan permission |
| `009` | Menu dan seed navigasi |
| `010` | Pengerasan constraint unik (`uq_stock_transfer_lines_transfer_item`) dan indeks performa Fase 1 |
| `011` | Optimasi indeks komposit pencarian & filter `audit_logs` Fase 1 |
| `012` *(Fase 2 — M9)* | Tabel `plans`, `tenants`, `platform_admins`, `platform_refresh_tokens`, `settings`, dan seed paket kuota awal |
| `013` *(Fase 2 — M9)* | Penambahan `tenant_id`, *Composite FK* `(tenant_id, <fk>_id)`, constraint `UNIQUE (tenant_id, ...)`, dan PostgreSQL RLS pada 24 tabel bisnis |

Migration yang sudah diterapkan (`001`–`011`) tidak diedit; transisi Multi-Tenant Fase 2 menggunakan berkas baru `012` dan `013`.

## 6. Spesifikasi teknis migrasi Fase 2 (M9 — Multi-Tenant SaaS)

Untuk menjamin migrasi *forward-only* `012_create_tenants_settings.sql` dan `013_add_tenant_scope.sql` berjalan tanpa konflik pada PostgreSQL, rancangan skema wajib mengikuti empat aturan teknis berikut:

1. **Penanganan Trigger Imutabilitas (`007`) saat Backfill `013_add_tenant_scope.sql`:**
   - Karena `stock_movements` dan `audit_logs` dilindungi oleh trigger `trg_stock_movements_immutable` dan `trg_audit_logs_immutable` (yang menolak setiap `UPDATE`), skrip migrasi `013` (dijalankan oleh role pemilik tabel di dalam satu blok transaksi) wajib melakukan:
     - `ALTER TABLE stock_movements DISABLE TRIGGER trg_stock_movements_immutable;`
     - `ALTER TABLE audit_logs DISABLE TRIGGER trg_audit_logs_immutable;`
     - melakukan *backfill* `UPDATE ... SET tenant_id = <default_tenant_id>` lalu memasang `ALTER COLUMN tenant_id SET NOT NULL`, dan
     - mengaktifkan kembali kedua trigger (`ENABLE TRIGGER`) sebelum transaksi migrasi selesai.
2. **Prasyarat `UNIQUE (tenant_id, id)` untuk *Composite Foreign Key* (`BR-GLB-019`):**
   - Sebelum mengganti Foreign Key tunggal menjadi *Composite FK* `(tenant_id, <fk>_id)`, migrasi `013` wajib menambahkan constraint `uq_<table>_tenant_id UNIQUE (tenant_id, id)` pada seluruh tabel induk: `roles`, `users`, `menus`, `categories`, `uoms`, `suppliers`, `items`, `warehouses`, `storage_locations` (beserta `UNIQUE (tenant_id, id, warehouse_id)`), `purchase_orders`, `po_lines`, `goods_receipts`, `stock_transfers`, dan `stock_opnames`.
3. **Transformasi 14 Constraint `UNIQUE`/`PK` Global Menjadi Per-Tenant (`BR-GLB-021`):**
   - Constraint global berikut di-`DROP` dan dibuat ulang dengan awalan `tenant_id`:
     `uq_roles_name`, `uq_users_username`, `uq_users_email`, `uq_menus_code`, `uq_categories_name`, `uq_uoms_code`, `uq_suppliers_code`, `uq_items_sku`, `uq_warehouses_code`, `uq_purchase_orders_po_number`, `uq_goods_receipts_gr_number`, `uq_stock_transfers_transfer_number`, `uq_stock_opnames_opname_number`, serta `pk_document_sequences (tenant_id, doc_type, period)`.
4. **Kebijakan PostgreSQL Row-Level Security (RLS):**
   - Seluruh tabel ber-`tenant_id` mengaktifkan `ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;` dan `FORCE ROW LEVEL SECURITY;` dengan ekspresi kebijakan `tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint`.

## 7. Traceability

| Requirement PRD General | Database support | AC terkait |
| --- | --- | --- |
| `FR-PLT-001`, `FR-PLT-005` | `document_sequences` (`(doc_type, period)` / `(tenant_id, doc_type, period)` pada M9), `schema_migrations` | `AC-15`, `AC-18`, `AC-27` |
| `FR-IAM-001..009` | IAM tables, `token_hash`, active/lockout fields, `user_warehouses`, `menus` | `AC-05`, `AC-11`, `AC-12`, `AC-14` |
| `FR-AUD-001..002` | Append-only `audit_logs` (tanpa hak `UPDATE`/`DELETE` bagi `wms_app`) | `AC-05`, `AC-07`, `AC-08`, `AC-22` |
| `FR-MST-001..005` | Master tables dengan case-insensitive uniqueness, `allow_decimal`, `is_active`, dan FK | `AC-19`, `AC-27` |
| `FR-MST-006..007` | `items`, `suppliers`, `audit_logs` (tanpa tabel/kolom baru); unique index case-insensitive `sku`/`code` menjadi sumber kebenaran duplikasi konkuren | `AC-30`, `AC-31` |
| `FR-WHS-001..003` | `warehouses` (`allow_negative_stock`), `storage_locations` dengan unique `(id, warehouse_id)` | `AC-12`, `AC-20` |
| `FR-INV-001..006` | `inventory_balances` (`(warehouse_id, location_id, item_id)`), append-only `stock_movements`, `NUMERIC(18,4)` | `AC-02`, `AC-03`, `AC-04`, `AC-06`, `AC-08`, `AC-13`, `AC-16` |
| `FR-PUR-001..004`, `FR-RCV-001..004` | PO/GR headers dan lines, unique `(po_id, item_id)`, composite location FK, status checks | `AC-01`, `AC-07`, `AC-13`, `AC-21` |
| `FR-TRF-001..005`, `FR-OPN-001..006` | Transfer/opname headers dan lines, unique line keys, composite location FK, snapshot/variance fields | `AC-02`, `AC-03`, `AC-04`, `AC-06`, `AC-09`, `AC-10`, `AC-21` |
| `FR-TNT-001..006` *(Fase 2 — M9)* | `plans`, `tenants`, `platform_admins`, `platform_refresh_tokens`, kolom `tenant_id`, *Composite FK*, dan kebijakan RLS | `AC-23` s.d. `AC-25`, `AC-27` s.d. `AC-29` |
| `FR-CFG-001..004` *(Fase 2 — M9)* | `settings` dengan unique `(tenant_id, COALESCE(warehouse_id, 0), key)` | `AC-26` |

## 8. Perlu ditinjau

- Target partitioning/retention untuk ledger dan audit belum ditetapkan.
- SLA backup, recovery point, dan recovery time belum ditentukan.
- Migrasi `010` dan `011` termasuk baseline Fase 1 dan sudah tersedia di `db/migrations/`; migrasi Fase 2 (M9) dimulai dari `012`.
