# Acuan Struktur Folder & Arsitektur Kode — WMS API

Dokumen pendamping `PRODUCT_REQUIREMENTS_DOCUMENT.md` (keduanya disimpan di folder `docs/core`). Struktur ini untuk FastAPI + PostgreSQL yang diakses langsung (psycopg 3, tanpa ORM). Setiap kode FR, AC, permission, status, dan kode error di sini merujuk ke PRD v2.

---

## 1. Pohon Folder

```
warehouse_api/
├── AGENTS.md                       # aturan kerja untuk AI coding agent (harus di root repositori)
├── docs/core/
│   ├── PRODUCT_REQUIREMENTS_DOCUMENT.md                   # sumber kebenaran: apa yang dibangun
│   ├── FOLDER_STRUCTURE.md         # dokumen ini
│   └── schema_database.sql         # (opsional) hasil pg_dump --schema-only; referensi baca saja, bukan sumber kebenaran
├── app/
│   ├── main.py                     # bikin FastAPI(), lifespan (buka/tutup pool), daftarkan middleware, router & exception handler
│   │
│   ├── core/                       # fondasi teknis, tidak tahu soal bisnis gudang
│   │   ├── config.py               # Settings (pydantic-settings) dari .env
│   │   ├── database.py             # ConnectionPool, dependency get_conn
│   │   ├── security.py             # hash/verify password (argon2), buat/decode JWT, hash refresh token
│   │   ├── permissions.py          # konstanta kode permission + require_permission()
│   │   ├── exceptions.py           # DomainError + turunannya (InsufficientStock, OverReceipt, dst.)
│   │   ├── logging.py              # log terstruktur; membaca request id dari contextvar
│   │   └── middleware.py           # middleware request id (X-Request-ID); CORS dipasang di main.py bila perlu
│   │
│   ├── schemas/                    # Pydantic: bentuk request/response (bukan bentuk tabel)
│   │   ├── common.py               # Page[T], ErrorResponse, tipe Decimal -> string
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── menu.py                 # menu navigasi & pohon menu (my-menu)
│   │   ├── master.py               # category, uom, item, supplier
│   │   ├── warehouse.py            # warehouse, storage_location
│   │   ├── stock.py                # saldo stok, in-transit, ledger
│   │   ├── purchase_order.py
│   │   ├── goods_receipt.py
│   │   ├── stock_transfer.py
│   │   ├── stock_opname.py
│   │   └── audit_log.py
│   │
│   ├── api/                        # lapisan HTTP, setipis mungkin
│   │   ├── deps.py                 # get_current_user (verifikasi JWT + cek is_active/role dari DB)
│   │   └── routes/
│   │       ├── health.py
│   │       ├── auth.py             # login, refresh, logout, me, change-password
│   │       ├── users.py            # user, role/permission, penugasan gudang
│   │       ├── menus.py            # pohon menu frontend (my-menu) & CRUD menu
│   │       ├── master.py           # category, uom, item, supplier
│   │       ├── warehouses.py       # warehouse + storage_location
│   │       ├── stock.py            # saldo stok & ledger (read-only)
│   │       ├── purchase_orders.py
│   │       ├── goods_receipts.py
│   │       ├── stock_transfers.py
│   │       ├── stock_opnames.py
│   │       └── audit_logs.py
│   │
│   ├── services/                   # use case + aturan bisnis; pemilik batas transaksi
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── menu_service.py         # pohon menu terfilter permission & CRUD menu
│   │   ├── access_service.py       # ensure_warehouse_access(): cek penugasan gudang (3.2 PRD)
│   │   ├── master_service.py
│   │   ├── warehouse_service.py
│   │   ├── stock_service.py        # query tampilan stok (read-only)
│   │   ├── inventory_service.py    # apply_movement(): SATU-SATUNYA pintu ubah stok + tulis ledger
│   │   ├── po_service.py
│   │   ├── gr_service.py
│   │   ├── transfer_service.py
│   │   ├── opname_service.py
│   │   ├── audit_service.py        # record(): catat old_values/new_values
│   │   └── numbering_service.py    # nomor dokumen PO-202610-0001 dst.
│   │
│   ├── repositories/               # SATU-SATUNYA tempat string SQL berada
│   │   ├── user_repo.py
│   │   ├── token_repo.py           # refresh_tokens
│   │   ├── permission_repo.py      # roles, permissions, role_permissions, user_warehouses
│   │   ├── menu_repo.py            # menus
│   │   ├── master_repo.py
│   │   ├── warehouse_repo.py
│   │   ├── inventory_repo.py       # ensure row, lock balance, update balance, insert ledger, query stok
│   │   ├── po_repo.py
│   │   ├── gr_repo.py
│   │   ├── transfer_repo.py
│   │   ├── opname_repo.py          # termasuk query freeze lokasi
│   │   ├── audit_repo.py
│   │   └── sequence_repo.py        # document_sequences
│   │
│   └── utils/
│       ├── enums.py                # status PO/GR/Transfer/Opname, MovementType, ReferenceType
│       └── pagination.py           # parsing limit/offset, builder ORDER BY aman (whitelist kolom)
│
├── db/
│   ├── init/
│   │   └── 001_create_app_role.sql         # sekali jalan: role `wms_app` (bukan superuser, bukan pemilik tabel)
│   ├── migrations/
│   │   ├── 001_create_auth_tables.sql      # roles, permissions, role_permissions, users, user_warehouses, refresh_tokens
│   │   ├── 002_create_master_tables.sql    # categories, uoms, items, suppliers, warehouses, storage_locations
│   │   ├── 003_create_inventory_tables.sql # inventory_balances, stock_movements
│   │   ├── 004_create_purchasing_tables.sql# purchase_orders, po_lines, goods_receipts, gr_lines
│   │   ├── 005_create_transfer_opname.sql  # stock_transfers(+lines), stock_opnames(+lines)
│   │   ├── 006_create_audit_sequences.sql  # audit_logs, document_sequences
│   │   ├── 007_append_only_guards.sql      # trigger tolak UPDATE/DELETE + REVOKE hak wms_app (AC-08)
│   │   ├── 008_seed_roles_permissions.sql  # 5 role, kode permission, pemetaan (Matriks 3.1 PRD)
│   │   └── 009_create_menu_tables.sql      # tabel menus + seed menu awal modul WMS
│   ├── seeds/
│   │   └── dev_seed.sql                    # data contoh untuk pengembangan lokal
│   └── migrate.py                          # runner: jalankan .sql berurutan, catat di schema_migrations
│
├── scripts/
│   └── create_superadmin.py        # bootstrap user Super Admin pertama (belum ada user untuk login)
│
├── tests/
│   ├── conftest.py                 # DB test, migrasi, reset data antar test, fixture user per role
│   ├── factories.py                # helper insert data (gudang, lokasi, item, PO, saldo)
│   ├── test_auth.py                # AC-11
│   ├── test_menus.py               # AC-14
│   ├── test_rbac_scoping.py        # AC-05, AC-12
│   ├── test_goods_receipt.py       # AC-01, AC-07, AC-13
│   ├── test_stock_transfer.py      # AC-02, AC-03, AC-06, AC-09
│   ├── test_stock_opname.py        # AC-04, AC-10
│   └── test_immutability.py        # AC-08
│
├── .env.example
├── .gitignore
├── docker-compose.yml              # postgres (+ api bila mau); mount db/init ke initdb.d
├── Dockerfile
├── pyproject.toml                  # atau requirements.txt + pytest.ini
└── README.md
```

Paket yang dibutuhkan: `fastapi`, `uvicorn[standard]`, `psycopg[binary,pool]`, `pydantic-settings`, `argon2-cffi`, `pyjwt`; untuk pengembangan `pytest` dan `httpx`.

---

## 2. Aturan per Lapisan

Arah ketergantungan hanya satu: **routes → services → repositories → core/database**. Tidak boleh mundur (repository tidak boleh memanggil service, service tidak boleh meng-*import* routes).

| Lapisan | Boleh | Tidak boleh |
| --- | --- | --- |
| **routes** | Parse request, `Depends(require_permission("..."))`, memanggil **satu** fungsi service, mengembalikan schema. | SQL, aturan bisnis, `commit`, mengatur status HTTP error manual untuk aturan bisnis. |
| **services** | Aturan bisnis, urutan langkah use case, membuka transaksi, memanggil repository & service lain, melempar `DomainError`. | Meng-*import* FastAPI/HTTP, menulis string SQL. |
| **repositories** | SQL berparameter, menerima `conn` sebagai argumen, mengembalikan `dict` baris. | Keputusan bisnis, membuka/commit transaksi sendiri. |
| **schemas** | Validasi bentuk data masuk/keluar. | Logika bisnis, akses DB. |
| **core** | Konfigurasi, pool, keamanan, definisi exception. | Mengetahui detail modul gudang. |

Dua jenis pemeriksaan akses dipisah:

* **Permission (level peran):** di route lewat `require_permission("po:issue")`. Gagal → 403 `PERMISSION_DENIED`.
* **Warehouse scoping (level data):** di service lewat `access_service.ensure_warehouse_access(conn, actor, warehouse_id)`, karena gudangnya baru diketahui setelah dokumen dibaca. Gagal → 403 `WAREHOUSE_NOT_ASSIGNED`.

Middleware dibatasi pada hal lintas-request yang tidak butuh konteks bisnis: *request id* (`core/middleware.py`) dan CORS bila diperlukan. Hal lain **bukan** middleware: autentikasi dan permission adalah *dependency*, penanganan error adalah *exception handler* di `main.py`, sedangkan audit log dan transaksi berada di service.

---

## 3. Pola Koneksi & Transaksi

Pakai `def` biasa (bukan `async def`) pada route karena driver sinkron; FastAPI menjalankannya di *threadpool*. Jangan mencampur pola sinkron dan `async` dalam satu aplikasi. Jika kelak ingin `async`, pakai `AsyncConnectionPool` dan `async def` secara menyeluruh.

```python
# app/core/database.py
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=2, max_size=10,
    kwargs={"autocommit": True, "row_factory": dict_row},
    open=False,                      # dibuka/ditutup di lifespan main.py
)

def get_conn():
    with pool.connection() as conn:
        yield conn
```

Koneksi memakai `autocommit=True` agar pembacaan di luar transaksi (misalnya `get_current_user`) tidak diam-diam membuka transaksi panjang. **Batas transaksi dipegang oleh service**, tepat satu blok per use case:

```python
# app/services/gr_service.py
def post_goods_receipt(conn, gr_id: int, actor: dict) -> dict:
    with conn.transaction():         # BEGIN ... COMMIT; exception -> ROLLBACK seluruhnya
        ...                          # semua langkah use case di sini
```

Karena commit terjadi di dalam service sebelum response dikirim, tidak ada ketergantungan pada waktu eksekusi bagian akhir dependency `yield` milik FastAPI.

---

## 4. Pola Use Case Perubahan Stok

### 4.1. `inventory_service.apply_movement(conn, ...)`

Satu fungsi untuk semua perubahan stok (GR, Transfer, Opname). Harus dipanggil **di dalam transaksi**. Langkahnya:

1. **Kunci lokasi** (`SELECT ... FROM storage_locations WHERE id = %s FOR SHARE`), lalu periksa pembekuan Opname (`opname_repo.is_location_frozen`). Tipe `ADJUSTMENT_*` melewati pemeriksaan pembekuan, karena justru terjadi saat lokasi dibekukan.
2. **Pastikan baris saldo ada:** `INSERT INTO inventory_balances (...) VALUES (..., 0) ON CONFLICT (warehouse_id, location_id, item_id) DO NOTHING`.
3. **Kunci baris saldo:** `SELECT qty_on_hand ... FOR UPDATE` → `qty_before`.
4. **Validasi stok negatif:** jika `qty_change < 0` dan gudang `allow_negative_stock = FALSE` dan `qty_before + qty_change < 0` → lempar `InsufficientStock`.
5. **Update saldo:** `UPDATE inventory_balances SET qty_on_hand = qty_after ...`.
6. **Tulis ledger:** `INSERT INTO stock_movements (movement_type, ..., qty_before, qty_change, qty_after, reference_type, reference_id, created_by)`.

Pemeriksaan pembekuan di langkah 1 sengaja dilakukan setelah kunci lokasi didapat: Opname yang baru dimulai mengunci lokasi dengan `FOR UPDATE`, sehingga pemeriksaan ini tidak bisa "kebablasan" lolos di antara dua transaksi yang berjalan bersamaan.

### 4.2. Urutan penguncian (PRD 6.5)

Semua use case mengunci dengan urutan yang sama agar tidak terjadi *deadlock*:

1. Baris *header* dokumen yang diproses (`FOR UPDATE`) lalu cek statusnya.
2. Baris PO terkait (`FOR UPDATE`), bila ada.
3. Baris lokasi penyimpanan (`FOR SHARE`; `FOR UPDATE` saat Opname dimulai), diurutkan berdasarkan `id`.
4. Baris saldo stok, diurutkan berdasarkan `(warehouse_id, location_id, item_id)`.

Service pemanggil bertugas **mengurutkan baris dokumen** sebelum memanggil `apply_movement` berulang kali.

### 4.3. Kerangka use case `post_goods_receipt`

```
with conn.transaction():
    1. gr  = gr_repo.lock_by_id(gr_id)              -> status harus DRAFT, kalau tidak: InvalidStateTransition
    2. access_service.ensure_warehouse_access(actor, gr.warehouse_id)
    3. po  = po_repo.lock_by_id(gr.po_id)           -> status harus ISSUED / PARTIALLY_RECEIVED
    4. po_lines = po_repo.lock_lines(po.id)         -> hitung ulang over-receipt (OverReceipt bila melebihi)
    5. untuk setiap baris GR (urut): inventory_service.apply_movement(IN_PURCHASE, +qty, ref=GR)
    6. po_repo.add_received(...)                     -> qty_received bertambah
    7. po_repo.update_status(...)                    -> PARTIALLY_RECEIVED / RECEIVED (semua baris penuh)
    8. gr_repo.mark_posted(...)
    9. audit_service.record(...)                     -> GR dan PO, old_values & new_values
```

Pola yang sama dipakai oleh `ship_transfer`, `receive_transfer`, dan `complete_opname`, hanya isi langkahnya yang berbeda.

---

## 5. Pemetaan Modul PRD ke File

| Modul (FR) | Route | Service | Repository | Schema | Migrasi |
| --- | --- | --- | --- | --- | --- |
| Autentikasi (FR-01) | `auth.py` | `auth_service` | `user_repo`, `token_repo` | `auth` | 001 |
| Pengguna, role, penugasan gudang | `users.py` | `user_service`, `access_service` | `user_repo`, `permission_repo` | `user` | 001, 008 |
| Menu navigasi (FR-01) | `menus.py` | `menu_service` | `menu_repo` | `menu` | 009 |
| Master data (FR-02) | `master.py`, `warehouses.py` | `master_service`, `warehouse_service` | `master_repo`, `warehouse_repo` | `master`, `warehouse` | 002 |
| Stok & in-transit (FR-03) | `stock.py` | `stock_service` | `inventory_repo` | `stock` | 003 |
| Purchase Order (FR-04) | `purchase_orders.py` | `po_service` | `po_repo` | `purchase_order` | 004 |
| Goods Receipt (FR-05) | `goods_receipts.py` | `gr_service` | `gr_repo`, `po_repo` | `goods_receipt` | 004 |
| Transfer Stok (FR-06) | `stock_transfers.py` | `transfer_service` | `transfer_repo` | `stock_transfer` | 005 |
| Stock Opname (FR-07) | `stock_opnames.py` | `opname_service` | `opname_repo` | `stock_opname` | 005 |
| Ledger (FR-08) | `stock.py` | `inventory_service`, `stock_service` | `inventory_repo` | `stock` | 003, 007 |
| Audit Log (FR-09) | `audit_logs.py` | `audit_service` | `audit_repo` | `audit_log` | 006, 007 |
| Penomoran dokumen (FR-10) | — | `numbering_service` | `sequence_repo` | — | 006 |
| Pagination (FR-11) | semua route daftar | — | — | `common` | — |

---

## 6. Konvensi

* **Penamaan file & fungsi:** `snake_case`. Fungsi service = kata kerja use case (`issue_po`, `post_goods_receipt`, `ship_transfer`, `approve_opname`). Fungsi repository diawali `get_`, `list_`, `insert_`, `update_`, `lock_`.
* **Penamaan schema:** `XxxCreate`, `XxxUpdate`, `XxxOut`. Kuantitas bertipe `Decimal` dan diserialisasi sebagai string.
* **Error:** semua aturan bisnis dilempar sebagai turunan `DomainError` yang membawa `code` dan `http_status`; satu *exception handler* di `main.py` mengubahnya menjadi format `{ "error": { "code", "message", "details" } }`. Daftar kode ada di Lampiran B PRD.
* **Status dokumen:** konstanta di `utils/enums.py`; setiap transisi dicek lewat satu tabel transisi yang diizinkan per dokumen, sehingga selaras dengan bagian 5.1 PRD.
* **ORDER BY dinamis:** hanya dari *whitelist* kolom (`utils/pagination.py`); nilai filter selalu lewat parameter query.
* **Migrasi:** nama `NNN_deskripsi.sql`, *forward-only*, tidak pernah mengubah berkas yang sudah diterapkan; perubahan baru = berkas baru.

---

## 7. Konfigurasi (`.env.example`)

```
DATABASE_URL=postgresql://wms_app:...@localhost:5432/wms          # role aplikasi (tanpa hak UPDATE/DELETE di tabel append-only)
MIGRATION_DATABASE_URL=postgresql://wms_owner:...@localhost:5432/wms  # pemilik skema, hanya untuk migrasi & seed
JWT_SECRET=ganti-dengan-string-acak-minimal-32-byte
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15
TEST_DATABASE_URL=postgresql://wms_owner:...@localhost:5432/wms_test
```

---

## 8. Catatan Pengujian

* Uji memakai **PostgreSQL sungguhan** (`wms_test`), bukan *mock*, karena yang diuji justru perilaku transaksi, *locking*, *trigger*, dan *constraint*.
* Pola "rollback tiap test" **tidak cukup** untuk AC-06 dan AC-13, karena skenario konkurensi membutuhkan beberapa koneksi terpisah (misalnya dua *thread*, masing-masing satu koneksi dari pool) yang saling melihat data yang sudah di-*commit*. Gunakan pereset data antar test (`TRUNCATE ... RESTART IDENTITY CASCADE`) lewat koneksi pemilik skema.
* AC-08 harus dijalankan dengan koneksi **role aplikasi** (`wms_app`); dengan role pemilik tabel, `UPDATE`/`DELETE` tetap dihalangi oleh *trigger*, tetapi pengujian hak akses menjadi tidak bermakna.
* Setiap test AC memberi nama fungsi yang memuat kode AC-nya (`test_ac06_concurrent_ship_only_one_succeeds`) agar mudah ditelusuri ke PRD.

---

## 9. Urutan Implementasi yang Disarankan

| Tahap | Isi | Selesai bila |
| --- | --- | --- |
| **M0 Fondasi** | Kerangka proyek, `config.py`, pool, middleware *request id*, `health`, `migrate.py`, docker-compose Postgres. | `GET /health` hidup dan migrasi kosong berjalan. |
| **M1 Skema** | Migrasi 001–009 ditulis tangan: tabel, FK komposit, `UNIQUE`, `CHECK`, indeks, *trigger* append-only, seed role/permission, dan seed menu. | Coba `UPDATE stock_movements` lewat `psql` dengan role `wms_app` → ditolak; menu awal tersedia. |
| **M2 Auth & Audit dasar** | Login, rotasi *refresh token*, `require_permission`, `audit_service`, `create_superadmin.py`. | AC-11 lulus. |
| **M3 Master & penugasan** | CRUD master, aturan penonaktifan, `access_service`. | AC-12 (bagian akses) lulus. |
| **M4 Inti stok** | `inventory_service.apply_movement`, `stock_service`, penomoran dokumen. | Uji langsung `apply_movement` dengan dua *thread* menunjukkan penguncian bekerja. |
| **M5 PO & GR** | PO lengkap, GR, posting atomik. | AC-01, AC-07, AC-13 lulus. |
| **M6 Transfer** | Alur `DRAFT → APPROVED → SHIPPED → RECEIVED`, selisih penerimaan. | AC-02, AC-03, AC-06, AC-09 lulus. |
| **M7 Opname** | *Snapshot*, pembekuan lokasi, persetujuan/penolakan, penyesuaian. | AC-04, AC-10 lulus. |
| **M8 Pengerasan** | Tinjau seluruh AC, `EXPLAIN ANALYZE` pada query stok & ledger, periksa indeks, log dan *request id*. | Seluruh AC-01 s.d. AC-14 hijau; baca stok < 200 ms pada data uji. |
