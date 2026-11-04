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

| Domain | Entitas/tabel | Keterkaitan PRD |
| --- | --- | --- |
| IAM | `roles`, `permissions`, `role_permissions`, `users`, `refresh_tokens`, `menus` | FR-01, AC-11, AC-14 |
| Master | `categories`, `uoms`, `suppliers`, `items` | FR-02 |
| Warehouse | `warehouses`, `user_warehouses`, `storage_locations` | FR-02, warehouse scoping |
| Inventory | `inventory_balances`, `stock_movements` | FR-03, FR-08 |
| Purchasing | `purchase_orders`, `po_lines` | FR-04 |
| Receiving | `goods_receipts`, `gr_lines` | FR-05 |
| Transfer | `stock_transfers`, `stock_transfer_lines` | FR-06 |
| Opname | `stock_opnames`, `stock_opname_lines` | FR-07 |
| Governance | `audit_logs`, `document_sequences`, `schema_migrations` | FR-09, FR-10 |

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

Migration yang sudah diterapkan tidak diedit; perubahan membutuhkan file baru.

## 6. Traceability

| Requirement | Database support |
| --- | --- |
| FR-01 | IAM tables, token hash, active/lock fields |
| FR-02 | Master and warehouse tables with active flags and FKs |
| FR-03/08 | Balance key, movement ledger, numeric quantity |
| FR-04/05 | PO/GR headers, lines, status, and references |
| FR-06/07 | Transfer/opname headers, lines, freeze and approval data |
| FR-09 | Append-only audit table |
| FR-10 | Period sequence table |
| AC-06/07/13 | Transaction boundaries, indexes, and row locks |

## 7. Perlu ditinjau

- Target partitioning/retention untuk ledger dan audit belum ditetapkan.
- SLA backup, recovery point, dan recovery time belum ditentukan.
- Perubahan schema untuk multi-tenant atau reporting tidak boleh dibuat sebelum
  keputusan scope pada PRD General disetujui.
