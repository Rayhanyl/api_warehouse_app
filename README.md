# Warehouse Management System (WMS) — REST API

Layanan REST API manajemen gudang multi-lokasi (*multi-warehouse & bin location*) berbasis **Python**, **FastAPI**, dan **PostgreSQL** (akses SQL langsung via `psycopg` 3 tanpa ORM). Dirancang untuk memberikan kontrol operasional persediaan secara *real-time*, akurat, aman terhadap akses konkuren (*row-level locking*), dan memiliki ketertelusuran penuh (*append-only stock ledger & audit log*).

---

## Fitur Utama (Ruang Lingkup MVP)

1. **Autentikasi, RBAC & Warehouse Scoping:**
   * Autentikasi JWT (*Access Token* 15 menit & *Refresh Token* 7 hari dengan rotasi serta deteksi penggunaan ulang token yang dicabut).
   * Penguncian akun sementara setelah 5 kali gagal login berturut-turut.
   * 5 Peran (*Super Admin*, *Warehouse Manager*, *Purchasing Staff*, *Warehouse Staff*, *Auditor*) dengan 24 kode *permission* granular dan pembatasan penugasan gudang (*warehouse scoping*).
2. **Master Data:**
   * Kategori, Satuan Ukur (*UoM* dengan pengaturan `allow_decimal`), Barang (*Item* dengan SKU unik), Pemasok (*Supplier*), Gudang (*Warehouse* dengan pengaturan `allow_negative_stock`), dan Lokasi Penyimpanan (*Storage Location / Bin*).
   * Tanpa penghapusan permanen (*soft deactivate* via `is_active` dengan validasi saldo & dokumen aktif).
3. **Purchase Order (PO) & Goods Receipt (GR):**
   * Siklus PO (`DRAFT` → `ISSUED` → `PARTIALLY_RECEIVED` / `RECEIVED` / `CLOSED` / `CANCELLED`).
   * Penerimaan barang bertahap (parsial) maupun penuh terhadap PO dengan pencegahan *over-receipt* di bawah penguncian baris (`SELECT ... FOR UPDATE`).
4. **Transfer Stok Antar-Gudang / Antar-Lokasi:**
   * Siklus dua tahap fisik eksplisit (`DRAFT` → `APPROVED` → `SHIPPED` → `RECEIVED` / `CANCELLED`) untuk melacak stok dalam perjalanan (*in-transit*).
   * Pencatatan selisih penerimaan (`qty_received < qty`) dengan kewajiban alasan selisih (`variance_reason`).
5. **Stock Opname & Saldo Awal:**
   * Pengambilan *snapshot* `qty_system` dan **pembekuan lokasi** otomatis selama sesi berlangsung (`IN_PROGRESS` / `WAITING_APPROVAL`).
   * Rekonsiliasi stok fisik dengan persetujuan *Warehouse Manager* (`COMPLETED` menghasilkan penyesuaian `ADJUSTMENT_PLUS` / `ADJUSTMENT_MINUS`), sekaligus menjadi mekanisme input saldo awal gudang.
6. **Imutabilitas Buku Besar & Audit Log:**
   * Tabel `stock_movements` dan `audit_logs` bersifat *append-only*, dilindungi oleh *trigger* PostgreSQL serta pencabutan hak `UPDATE`/`DELETE`/`TRUNCATE` pada role database aplikasi (`wms_app`).

---

## Teknologi Utama

| Komponen | Teknologi |
| --- | --- |
| Bahasa & Framework | Python 3.11+, FastAPI, Pydantic v2 (`pydantic-settings`) |
| Database & Driver | PostgreSQL 13+, `psycopg[binary,pool]` v3 (sinkron, tanpa ORM) |
| Keamanan | `PyJWT` (HS256), `argon2-cffi` (Argon2id password hashing) |
| Migrasi Database | Berkas `.sql` berurutan (*forward-only*) + runner `db/migrate.py` |
| Pengujian | `pytest`, `httpx` (diuji langsung terhadap PostgreSQL sungguhan) |

---

## Arsitektur & Struktur Proyek

Proyek mengikuti arsitektur berlapis satu arah: **`routes` → `services` → `repositories` → `core/database`**.

```text
warehouse_app/
├── app/
│   ├── main.py                     # Inisialisasi FastAPI, lifespan connection pool, router & exception handler
│   ├── core/                       # Konfigurasi (.env), connection pool, JWT/Argon2, permission, DomainError, logging
│   ├── schemas/                    # Kontrak request/response Pydantic (kuantitas Decimal diserialisasi sebagai string)
│   ├── api/
│   │   ├── deps.py                 # Dependency get_current_user (verifikasi JWT + cek status aktif & role di DB)
│   │   └── routes/                 # Endpoint HTTP tipis & pemeriksaan require_permission()
│   ├── services/                   # Logika bisnis, pemeriksaan warehouse scoping, pemilik transaksi (with conn.transaction():)
│   ├── repositories/               # Satu-satunya lapisan yang berisi query SQL berparameter
│   └── utils/                      # Enum status/tipe pergerakan & helper pagination (whitelist ORDER BY)
├── db/
│   ├── init/                       # Skrip inisialisasi role database aplikasi (wms_app)
│   ├── migrations/                 # Berkas migrasi SQL berurutan (001 s.d. 008)
│   ├── seeds/                      # Data contoh untuk pengembangan lokal (dev_seed.sql)
│   └── migrate.py                  # Runner migrasi SQL (mencatat versi di tabel schema_migrations)
├── scripts/
│   └── create_superadmin.py        # Bootstrap akun Super Admin pertama
├── tests/                          # Pengujian otomatis berbasis pytest terhadap database wms_test (AC-01 s.d. AC-13)
├── Product_requirements_document.MD
├── folder_structure.MD
├── schema_database.MD
└── AGENTS.md
```

---

## Persiapan & Cara Menjalankan Secara Lokal

### 1. Prasyarat

* **Python 3.11+**
* **PostgreSQL 13+** (lokal atau melalui Docker)

### 2. Instalasi Dependensi

Aktifkan *virtual environment* lalu pasang paket yang dibutuhkan:

```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1
pip install fastapi "uvicorn[standard]" "psycopg[binary,pool]" pydantic-settings argon2-cffi pyjwt pytest httpx
```

### 3. Konfigurasi Variabel Lingkungan (`.env`)

Salin berkas `.env.example` menjadi `.env` dan sesuaikan kredensial PostgreSQL serta kunci rahasia JWT:

```powershell
Copy-Item .env.example .env
```

Contoh isi `.env`:

```env
DATABASE_URL=postgresql://wms_app:password_app@localhost:5432/wms
MIGRATION_DATABASE_URL=postgresql://wms_owner:password_owner@localhost:5432/wms
JWT_SECRET=ganti-dengan-string-acak-minimal-32-byte
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15
TEST_DATABASE_URL=postgresql://wms_owner:password_owner@localhost:5432/wms_test
```

### 4. Menjalankan Migrasi Database & Bootstrap Super Admin

Jalankan migrasi skema menggunakan koneksi pemilik skema (`MIGRATION_DATABASE_URL`), lalu buat akun *Super Admin* pertama:

```powershell
python -m db.migrate
python scripts/create_superadmin.py
```

### 5. Menjalankan Server API

```powershell
uvicorn app.main:app --reload
```

Setelah server berjalan:
* **Swagger UI (OpenAPI):** `http://localhost:8000/docs`
* **ReDoc:** `http://localhost:8000/redoc`
* **Health Check:** `http://localhost:8000/api/v1/health` (atau `/health`)

---

## Pengujian (*Testing*)

Pengujian dijalankan terhadap database PostgreSQL sungguhan (`TEST_DATABASE_URL` / `wms_test`) untuk memverifikasi perilaku transaksi, *row-level locking*, konkurensi, *trigger* imutabilitas, dan *constraint* database:

```powershell
# Menjalankan seluruh pengujian
pytest

# Menjalankan pengujian untuk Acceptance Criteria tertentu (mis. AC-06 konkurensi pengiriman)
pytest -k ac06
```

---

## Dokumen Rujukan

* [Product_requirements_document.MD](file:///d:/Training/Python/warehouse_app/Product_requirements_document.MD) — Spesifikasi kebutuhan fungsional (FR-01 s.d. FR-11), matriks RBAC, siklus status dokumen, aturan validasi, kode error, dan kriteria penerimaan (AC-01 s.d. AC-13).
* [folder_structure.MD](file:///d:/Training/Python/warehouse_app/folder_structure.MD) — Arsitektur kode berlapis, pola koneksi/transaksi, urutan penguncian (*locking order*), dan tahapan implementasi (M0 s.d. M8).
* [schema_database.MD](file:///d:/Training/Python/warehouse_app/schema_database.MD) — Spesifikasi tabel, relasi *Composite Foreign Key*, DDL PostgreSQL lengkap (`001` s.d. `008`), serta *trigger* imutabilitas.
* [AGENTS.md](file:///d:/Training/Python/warehouse_app/AGENTS.md) — Aturan kerja dan batasan invarian bisnis yang wajib dipatuhi selama pengembangan.

