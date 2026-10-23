# Dokumen Rencana & Spesifikasi Pengujian (QA Test Plan) — WMS API

| Informasi Dokumen | Keterangan |
| --- | --- |
| **Produk** | Warehouse Management System (WMS) REST API |
| **Versi Acuan PRD** | v2.0 (`docs/core/PRODUCT_REQUIREMENTS_DOCUMENT.md`) |
| **Acuan Arsitektur** | `docs/core/FOLDER_STRUCTURE.md` & `AGENTS.md` |
| **Alat Pengujian** | `pytest`, `httpx`, PostgreSQL sungguhan (`psycopg` 3) |
| **Target Database Uji** | `wms_test` (terpisah dari database pengembangan `wms`) |

---

## 1. Tujuan & Filosofi Pengujian

Dokumen ini menjelaskan strategi, ruang lingkup, arsitektur pengujian, serta rincian skenario uji untuk memastikan implementasi **WMS API** memenuhi seluruh kebutuhan fungsional (FR-01 s.d. FR-11), aturan validasi bisnis (Bab 6 PRD), kebutuhan non-fungsional (Bab 7 PRD), dan kriteria penerimaan (**AC-01 s.d. AC-13**).

Prinsip utama pengujian pada proyek ini:

1. **Menggunakan PostgreSQL Sungguhan (Tanpa Mock Database):**
   Inti keandalan WMS berada pada perilaku transaksi database (`BEGIN ... COMMIT/ROLLBACK`), penguncian baris (`SELECT ... FOR UPDATE` dan `FOR SHARE`), *constraint* (`UNIQUE`, `CHECK`, *composite foreign key*), serta *trigger* database. Oleh karena itu, seluruh pengujian otomatis dijalankan langsung terhadap instance PostgreSQL sungguhan (`wms_test`).
2. **Pemisahan Role Database (`wms_owner` vs `wms_app`):**
   * `wms_owner` digunakan oleh *test runner* hanya untuk menjalankan migrasi skema awal dan mereset data antar pengujian (`TRUNCATE ... RESTART IDENTITY CASCADE`).
   * `wms_app` digunakan oleh aplikasi (dan pengujian imutabilitas AC-08) untuk memastikan hak akses level database benar-benar membatasi operasi destruktif pada tabel *append-only*.
3. **Pengujian Konkurensi Nyata:**
   Skenario balapan (*race condition*) seperti pengiriman stok bersamaan (AC-06) dan posting dokumen ganda (AC-13) tidak dapat diuji dengan pola *transaction rollback per test*. Pengujian dilakukan menggunakan beberapa koneksi independen dari *connection pool* yang dieksekusi secara paralel (misalnya menggunakan `ThreadPoolExecutor` + `threading.Barrier`) terhadap data yang sudah di-*commit*.

---

## 2. Lingkungan & Arsitektur Pengujian

### 2.1. Perangkat & Pustaka Uji
* **Test Runner:** `pytest`
* **HTTP Client:** `httpx` (`TestClient` / klien sinkron terhadap aplikasi FastAPI)
* **Database Driver:** `psycopg` 3 + `psycopg_pool` (sinkron, selaras dengan route `def` pada aplikasi)

### 2.2. Konfigurasi Lingkungan (`.env` Pengujian)
Pengujian menggunakan variabel lingkungan terpisah agar tidak pernah menyentuh database pengembangan maupun produksi:

```ini
TEST_DATABASE_URL=postgresql://wms_owner:...@localhost:5432/wms_test
DATABASE_URL=postgresql://wms_app:...@localhost:5432/wms_test
JWT_SECRET=test-secret-key-minimal-32-bytes-panjangnya
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15
```

### 2.3. Struktur Berkas Pengujian (`tests/`)

Sesuai `docs/core/FOLDER_STRUCTURE.md`, berkas pengujian disusun sebagai berikut:

| Berkas | Tanggung Jawab & Cakupan AC |
| --- | --- |
| `tests/conftest.py` | Setup database `wms_test`, eksekusi migrasi `001`–`008`, pembersihan tabel antar-test (`TRUNCATE ... RESTART IDENTITY CASCADE`), pembuatan *fixture* `client`, koneksi database, serta *fixture* pengguna beserta token untuk ke-5 peran (Super Admin, Warehouse Manager, Purchasing Staff, Warehouse Staff, Auditor). |
| `tests/factories.py` | Fungsi pembantu (*helper*) untuk menyiapkan data prasyarat secara cepat dan konsisten: gudang, lokasi penyimpanan, kategori, UoM, barang (item), pemasok, PO, maupun saldo stok awal. |
| `tests/test_auth.py` | Menguji siklus autentikasi, rotasi & pencabutan *Refresh Token*, deteksi *token reuse*, *logout*, dan penguncian akun (**AC-11**, FR-01). |
| `tests/test_rbac_scoping.py` | Menguji matriks *permission* untuk 5 peran, verifikasi status aktif/peran langsung dari DB setiap request, *warehouse scoping*, dan pencatatan *Audit Log* (**AC-05**, **AC-12**, FR-01, FR-09). |
| `tests/test_goods_receipt.py` | Menguji alur PO ke GR, penerimaan parsial & penuh, pencegahan *over-receipt*, atomisitas transaksi (*rollback* saat gagal di tengah), dan pencegahan posting GR ganda secara konkuren (**AC-01**, **AC-07**, **AC-13**, FR-04, FR-05). |
| `tests/test_stock_transfer.py` | Menguji alur Transfer Stok (`DRAFT` → `APPROVED` → `SHIPPED` → `RECEIVED`), pencegahan stok negatif, konsistensi stok *in-transit* & *ledger*, konkurensi pengiriman stok, dan aturan selisih penerimaan (**AC-02**, **AC-03**, **AC-06**, **AC-09**, FR-03, FR-06). |
| `tests/test_stock_opname.py` | Menguji siklus Stock Opname, pengambilan *snapshot* `qty_system`, pembekuan lokasi (*location freeze*), penambahan baris saldo awal (`qty_system = 0`), persetujuan/penolakan, dan rekonsiliasi saldo (**AC-04**, **AC-10**, FR-07). |
| `tests/test_immutability.py` | Menguji keabadian (*append-only*) tabel `stock_movements` dan `audit_logs` baik dari sisi izin role `wms_app` maupun *trigger* PostgreSQL (**AC-08**, FR-08, FR-09). |

---

## 3. Rincian Pengujian Kriteria Penerimaan (AC-01 s.d. AC-13)

Setiap Kriteria Penerimaan pada PRD Bagian 8 wajib memiliki minimal satu fungsi pengujian eksplisit yang memuat kode AC pada namanya.

### AC-01 — Penerimaan Parsial & Pemenuhan PO
* **Berkas:** `tests/test_goods_receipt.py`
* **Contoh Nama Test:** `test_ac01_partial_and_full_goods_receipt_fulfillment`
* **Prasyarat (*Given*):** PO berstatus `ISSUED` untuk 50 unit Barang X pada Gudang A.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Posting GR #1 sebesar `20.0000` unit → HTTP 200; status PO berubah menjadi `PARTIALLY_RECEIVED`; `po_lines.qty_received = 20.0000`; `inventory_balances.qty_on_hand = 20.0000`; tercatat 1 baris `stock_movements` bertipe `IN_PURCHASE` (`+20.0000`).
  2. Buat & coba posting GR #2 sebesar `35.0000` unit → Ditolak dengan **HTTP 409** dan kode error `OVER_RECEIPT` (karena `20 + 35 = 55 > 50`). Saldo stok tetap `20.0000` dan status PO tetap `PARTIALLY_RECEIVED`.
  3. Ubah/buat GR #2 sebesar `30.0000` unit lalu posting → HTTP 200; `po_lines.qty_received = 50.0000`; status PO otomatis menjadi `RECEIVED`; saldo stok menjadi `50.0000`.

### AC-02 — Pencegahan Stok Negatif
* **Berkas:** `tests/test_stock_transfer.py`
* **Contoh Nama Test:** `test_ac02_negative_stock_prevention_on_transfer_ship`
* **Prasyarat (*Given*):** Saldo Barang Y di Gudang A (Lokasi A1) = `10.0000` unit; Gudang A memiliki `allow_negative_stock = FALSE`; dokumen Transfer 12 unit dari Gudang A (Lokasi A1) ke Gudang B berstatus `APPROVED`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Eksekusi `POST /api/v1/stock-transfers/{id}/ship` → Ditolak dengan **HTTP 409** (`INSUFFICIENT_STOCK`) beserta detail barang, stok tersedia (`10.0000`), dan kuantitas diminta (`12.0000`).
  2. Verifikasi database: saldo di Lokasi A1 tetap `10.0000`, status Transfer tetap `APPROVED`, dan tidak ada baris `OUT_TRANSFER` baru di `stock_movements`.

### AC-03 — Konsistensi Transfer Antar-Gudang
* **Berkas:** `tests/test_stock_transfer.py`
* **Contoh Nama Test:** `test_ac03_inter_warehouse_transfer_consistency`
* **Prasyarat (*Given*):** Saldo awal Gudang A (Lokasi A1) = `50.0000`, Gudang B (Lokasi B1) = `0.0000`. Transfer 15 unit dari A1 ke B1 berstatus `APPROVED`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Eksekusi `POST /api/v1/stock-transfers/{id}/ship` → HTTP 200; status menjadi `SHIPPED`; stok Lokasi A1 berkurang menjadi `35.0000`; tercatat 1 baris `OUT_TRANSFER` (`qty_before=50`, `qty_change=-15`, `qty_after=35`); stok Lokasi B1 masih `0.0000`; endpoint stok menampilkan `in_transit = 15.0000`.
  2. Eksekusi `POST /api/v1/stock-transfers/{id}/receive` dengan `qty_received = "15.0000"` → HTTP 200; status menjadi `RECEIVED`; stok Lokasi B1 bertambah menjadi `15.0000`; tercatat 1 baris `IN_TRANSFER` (`qty_before=0`, `qty_change=+15`, `qty_after=15`); `in_transit` kembali `0.0000`.

### AC-04 — Rekonsiliasi Stock Opname
* **Berkas:** `tests/test_stock_opname.py`
* **Contoh Nama Test:** `test_ac04_stock_opname_reconciliation_adjustment_minus`
* **Prasyarat (*Given*):** Saldo Barang Z di Lokasi A1 tercatat `100.0000` unit. Sesi Opname dimulai (`IN_PROGRESS` → mengambil `qty_system = 100.0000`), petugas menginput `qty_physical = "97.0000"` dan mengajukan persetujuan (`WAITING_APPROVAL`).
* **Langkah & Ekspektasi (*When / Then*):**
  1. *Warehouse Manager* menyetujui opname (`POST /api/v1/stock-opnames/{id}/approve`) → HTTP 200; status Opname menjadi `COMPLETED`.
  2. Baris opname mencatat `qty_variance = "-3.0000"`.
  3. Saldo di `inventory_balances` diperbarui menjadi `97.0000`.
  4. Tercatat 1 baris `stock_movements` dengan `movement_type = 'ADJUSTMENT_MINUS'`, `qty_before = 100.0000`, `qty_change = -3.0000`, `qty_after = 97.0000`, `reference_type = 'STOCK_OPNAME'`.

### AC-05 — Kepatuhan RBAC & Audit Log
* **Berkas:** `tests/test_rbac_scoping.py`
* **Contoh Nama Test:** `test_ac05_rbac_enforcement_and_audit_log_recording`
* **Prasyarat (*Given*):** Pengguna dengan peran *Warehouse Staff* dan pengguna dengan peran *Purchasing Staff* / *Warehouse Manager*.
* **Langkah & Ekspektasi (*When / Then*):**
  1. *Warehouse Staff* mencoba menerbitkan PO (`POST /purchase-orders/{id}/issue`) atau menyetujui akhir Stock Opname (`POST /stock-opnames/{id}/approve`) → Ditolak dengan **HTTP 403** (`PERMISSION_DENIED`).
  2. Pengguna berwenang melakukan perubahan data yang sah (misalnya menerbitkan PO atau mengubah master barang) → HTTP 200; otomatis tercipta 1 baris baru di tabel `audit_logs` yang memuat `user_id`, `action`, `entity_type`, `entity_id`, `old_values`, `new_values`, `ip_address`, dan `created_at`.

### AC-06 — Konkurensi Pengiriman
* **Berkas:** `tests/test_stock_transfer.py`
* **Contoh Nama Test:** `test_ac06_concurrent_ship_only_one_succeeds`
* **Prasyarat (*Given*):** Saldo Barang Y di Lokasi A1 = `10.0000` unit (`allow_negative_stock = FALSE`). Dua dokumen Transfer berbeda (TRF-1 dan TRF-2) masing-masing meminta `8.0000` unit dari Lokasi A1, keduanya berstatus `APPROVED`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Dua *worker thread* disinkronkan dengan `threading.Barrier(2)` untuk memanggil `POST /stock-transfers/{id1}/ship` dan `POST /stock-transfers/{id2}/ship` secara bersamaan melalui koneksi database terpisah.
  2. Tepat **satu** request menghasilkan HTTP 200 (`SHIPPED`), dan **satu** request ditolak dengan **HTTP 409** (`INSUFFICIENT_STOCK`).
  3. Saldo akhir di Lokasi A1 adalah `2.0000` unit, dan hanya ada **1 baris** `OUT_TRANSFER` sebesar `-8.0000` pada `stock_movements`.

### AC-07 — Atomisitas Transaksi
* **Berkas:** `tests/test_goods_receipt.py`
* **Contoh Nama Test:** `test_ac07_transaction_atomicity_rollback_on_failure`
* **Prasyarat (*Given*):** Sebuah GR berstatus `DRAFT` untuk PO yang `ISSUED`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Simulasikan kegagalan di tengah eksekusi `post_goods_receipt` setelah perubahan stok tetapi sebelum transaksi selesai (misalnya dengan menyuntikkan kegagalan pada pemanggilan `audit_repo` / `audit_service.record` atau *ledger*).
  2. Permintaan gagal dan seluruh transaksi di-*rollback*.
  3. Verifikasi database: status GR tetap `DRAFT`, `inventory_balances.qty_on_hand` tidak bertambah, `po_lines.qty_received` tidak berubah, serta tidak ada baris baru yang tertinggal di `stock_movements` maupun `audit_logs`.

### AC-08 — Imutabilitas Buku Besar & Audit Log
* **Berkas:** `tests/test_immutability.py`
* **Contoh Nama Test:** `test_ac08_stock_movements_and_audit_logs_are_immutable`
* **Prasyarat (*Given*):** Terdapat baris data pada tabel `stock_movements` dan `audit_logs`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Menggunakan koneksi langsung ber-role `wms_app` (dan diuji pula terhadap *trigger* database), jalankan perintah SQL `UPDATE stock_movements SET qty_change = 999 WHERE id = ...` dan `DELETE FROM stock_movements WHERE id = ...`.
  2. Lakukan hal yang sama untuk `UPDATE audit_logs ...` dan `DELETE FROM audit_logs ...`.
  3. Seluruh operasi `UPDATE`, `DELETE`, maupun `TRUNCATE` ditolak oleh PostgreSQL (error *permission denied* atau *exception* dari *trigger* imutabilitas), dan isi kedua tabel tetap utuh tanpa perubahan.

### AC-09 — Selisih Penerimaan Transfer
* **Berkas:** `tests/test_stock_transfer.py`
* **Contoh Nama Test:** `test_ac09_transfer_receive_variance_validation_and_recording`
* **Prasyarat (*Given*):** Transfer 25 unit berstatus `SHIPPED` dari Gudang A ke Gudang B.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Terima Transfer dengan `qty_received = "26.0000"` → Ditolak **HTTP 409** (`TRANSFER_QTY_EXCEEDS_SHIPPED`).
  2. Terima Transfer dengan `qty_received = "23.0000"` tanpa `variance_reason` (kosong/null) → Ditolak **HTTP 422** (`VALIDATION_ERROR`).
  3. Terima Transfer dengan `qty_received = "23.0000"` dan `variance_reason = "2 unit rusak saat pengiriman"` → HTTP 200 (`RECEIVED`).
  4. Stok tujuan bertambah `23.0000` unit, tercatat 1 baris `IN_TRANSFER` sebesar `+23.0000` (tidak ada baris ledger untuk selisih 2 unit, dan stok asal tidak dikembalikan), serta baris Transfer menyimpan `qty_received = 23.0000` beserta alasan selisihnya.

### AC-10 — Pembekuan Lokasi Opname
* **Berkas:** `tests/test_stock_opname.py`
* **Contoh Nama Test:** `test_ac10_location_frozen_during_active_opname`
* **Prasyarat (*Given*):** Sesi Opname pada Lokasi X dimulai sehingga berstatus `IN_PROGRESS` (dan juga diuji saat `WAITING_APPROVAL`).
* **Langkah & Ekspektasi (*When / Then*):**
  1. Coba posting GR yang memasukkan barang ke Lokasi X → Ditolak **HTTP 409** (`LOCATION_FROZEN`).
  2. Coba kirim Transfer (`ship`) dari Lokasi X atau terima Transfer (`receive`) ke Lokasi X → Ditolak **HTTP 409** (`LOCATION_FROZEN`).
  3. Selesaikan Opname (`COMPLETED`) atau batalkan (`CANCELLED`) → Pembekuan lokasi lepas; posting GR dan pengiriman/penerimaan Transfer pada Lokasi X kini berhasil (HTTP 200).

### AC-11 — Siklus Refresh Token & Deteksi Pencurian
* **Berkas:** `tests/test_auth.py`
* **Contoh Nama Test:** `test_ac11_refresh_token_rotation_reuse_detection_and_logout`
* **Prasyarat (*Given*):** Pengguna berhasil login dan memperoleh *Refresh Token* `R1`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Gunakan `R1` pada `POST /api/v1/auth/refresh` → HTTP 200; terbit *Access Token* baru dan *Refresh Token* `R2`; status `R1` di database tercatat `revoked_at IS NOT NULL` dan `replaced_by_id` menunjuk ke `R2`.
  2. Gunakan kembali `R1` yang sudah dicabut pada `POST /api/v1/auth/refresh` → Ditolak **HTTP 401** (`AUTH_TOKEN_INVALID`); sistem mendeteksi penyalahgunaan token dan otomatis mencabut **seluruh** *Refresh Token* aktif milik pengguna tersebut (termasuk `R2`), serta mencatat insiden pada `audit_logs`.
  3. Coba gunakan `R2` setelah pencabutan massal → Ditolak **HTTP 401**.
  4. Login ulang untuk mendapat `R3`, lalu panggil `POST /api/v1/auth/logout` dengan `R3` → `R3` dicabut dan tidak bisa dipakai lagi untuk `refresh` (**HTTP 401**).

### AC-12 — Warehouse Scoping
* **Berkas:** `tests/test_rbac_scoping.py`
* **Contoh Nama Test:** `test_ac12_warehouse_scoping_blocks_unassigned_warehouse`
* **Prasyarat (*Given*):** Pengguna *Warehouse Staff* yang hanya ditugaskan pada **Gudang A** di tabel `user_warehouses`. Terdapat PO yang ditujukan ke **Gudang B**.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Pengguna tersebut mencoba membuat atau memposting GR untuk PO Gudang B → Ditolak **HTTP 403** dengan kode `WAREHOUSE_NOT_ASSIGNED`.
  2. Diuji juga untuk aksi bertanda **(g)** lainnya pada Matriks 3.1: `location:manage`, `transfer:create/approve/ship` (wajib ditugaskan di gudang asal), `transfer:receive` (wajib ditugaskan di gudang tujuan), `opname:manage/count/approve`, serta pembatasan pembacaan data bagi *Warehouse Staff*.

### AC-13 — Pencegahan Posting Ganda
* **Berkas:** `tests/test_goods_receipt.py`
* **Contoh Nama Test:** `test_ac13_concurrent_double_post_goods_receipt_prevented`
* **Prasyarat (*Given*):** Sebuah GR berstatus `DRAFT` sebesar `10.0000` unit.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Dua permintaan `POST /api/v1/goods-receipts/{id}/post` untuk ID GR yang sama dikirim secara bersamaan menggunakan 2 *thread* yang disinkronkan lewat `threading.Barrier(2)`.
  2. Karena baris header GR dikunci (`SELECT ... FOR UPDATE`) sebelum pemeriksaan status, tepat **satu** permintaan berhasil (HTTP 200, status `POSTED`) dan permintaan lainnya ditolak dengan **HTTP 409** (`INVALID_STATE_TRANSITION`).
  3. Saldo stok di gudang tujuan hanya bertambah `10.0000` unit (bukan 20), `po_lines.qty_received` hanya bertambah `10.0000`, dan hanya tercipta 1 baris `IN_PURCHASE` di `stock_movements`.

---

## 4. Cakupan Pengujian Fungsional & Aturan Bisnis Tambahan

Selain ke-13 AC utama di atas, suite pengujian juga mencakup validasi per modul sesuai FR-01 s.d. FR-11 dan Bab 6 PRD:

### 4.1. Keamanan & Autentikasi Tambahan (FR-01, Bab 6.4, 7.2)
* **Penguncian Akun (*Account Lockout*):** Gagal login 5 kali berturut-turut mengunci akun selama 15 menit; percobaan login berikutnya (meski password benar) ditolak dengan **HTTP 429** (`AUTH_TOO_MANY_ATTEMPTS`). Setiap gagal login tercatat di `audit_logs`.
* **Verifikasi Peran & Status Aktif per Request:** Jika pengguna sedang memegang *Access Token* yang belum kedaluwarsa lalu Super Admin menonaktifkan akun tersebut (`is_active = FALSE`) atau mengubah perannya di DB, request berikutnya langsung ditolak tanpa menunggu token 15 menit habis.
* **Kerahasiaan di Audit Log:** Memastikan perubahan pengguna, login, atau ganti password tidak pernah membocorkan `password`, `password_hash`, maupun token ke kolom `old_values`/`new_values` di `audit_logs`.

### 4.2. Master Data & Aturan Penonaktifan (FR-02, Bab 6.3, 6.8, 6.9)
* **Larangan Hard Delete:** Memastikan tidak ada endpoint `DELETE` permanen; penonaktifan menggunakan `is_active = FALSE`.
* **Perlindungan Entitas Sedang Dipakai (`ENTITY_IN_USE` - HTTP 409):**
  * Menolak penonaktifan gudang, lokasi, atau barang yang masih memiliki `qty_on_hand != 0` atau masih tercantum pada dokumen belum final (`DRAFT`, `ISSUED`, `PARTIALLY_RECEIVED`, `APPROVED`, `SHIPPED`, `IN_PROGRESS`, `WAITING_APPROVAL`).
  * Menolak penonaktifan pemasok yang masih memiliki PO belum final.
* **Imutabilitas SKU:** Mengubah `sku` barang yang sudah pernah dipakai di transaksi ditolak.
* **Aturan Desimal UoM (`allow_decimal`):** Jika barang memiliki UoM dengan `allow_decimal = FALSE`, input kuantitas pecahan (mis. `"5.2500"`) pada PO/GR/Transfer/Opname ditolak dengan **HTTP 422** (`VALIDATION_ERROR`).
* **Validasi Referensi & Lokasi:**
  * Memilih lokasi yang bukan milik gudang terkait atau tidak aktif → **HTTP 422** (`INVALID_LOCATION`).
  * Membuat dokumen dengan barang/gudang/pemasok nonaktif → **HTTP 422** (`INACTIVE_REFERENCE`).
  * Transfer dengan `(source_warehouse_id, source_location_id)` sama dengan tujuan → ditolak **HTTP 422**.
  * Duplikasi kode unik (SKU, kode gudang, kode lokasi dalam gudang yang sama, barang ganda dalam satu PO) → **HTTP 409** (`DUPLICATE`) atau **HTTP 422**.

### 4.3. Siklus Status Dokumen (Bab 5.1)
* Memastikan seluruh perubahan status hanya bisa melalui endpoint aksi (`/{id}/issue`, `/cancel`, `/close`, `/post`, `/approve`, `/ship`, `/receive`, `/start`, `/submit`, `/reject`).
* Menguji transisi tidak sah (misalnya membatalkan PO `ISSUED` yang sudah punya GR `POSTED`/`DRAFT`, menutup PO `ISSUED` tanpa alasan penutupan atau saat masih ada GR `DRAFT`, menolak Opname tanpa `rejection_reason`) → ditolak dengan **HTTP 409** (`INVALID_STATE_TRANSITION`) atau **HTTP 422** (`VALIDATION_ERROR`).

### 4.4. Saldo Awal, In-Transit, Presisi Numerik & Invarian Ledger (FR-03, FR-08, FR-10, FR-11)
* **Input Saldo Awal lewat Opname:** Menguji penambahan baris barang yang belum punya saldo (`qty_system = 0`) pada sesi Opname, diisi `qty_physical > 0`, lalu disetujui → menghasilkan `ADJUSTMENT_PLUS` dan membuat saldo awal.
* **Opsi `allow_negative_stock = TRUE`:** Menguji bahwa bila Super Admin mengaktifkan `allow_negative_stock = TRUE` pada suatu gudang, pengiriman Transfer diizinkan melewati 0 dan mencatat `qty_after` negatif di `stock_movements`.
* **Invarian Buku Besar:** Setelah rangkaian transaksi (GR, Transfer, Opname), memverifikasi bahwa untuk setiap `(warehouse_id, location_id, item_id)`:
  * Setiap baris memenuhi `qty_after = qty_before + qty_change`.
  * `qty_after` pada baris `stock_movements` terakhir persis sama dengan `inventory_balances.qty_on_hand`.
* **Presisi Kuantitas:** Memastikan seluruh respons JSON menyajikan kuantitas sebagai **string desimal** (contoh `"10.0000"`), bukan `float`.
* **Penomoran Dokumen (FR-10):** Memastikan nomor dokumen mengikuti format `{PREFIX}-{YYYYMM}-{NNNN}` (`PO`, `GR`, `TRF`, `OPN`), urut, aman saat dibuat bersamaan (konkuren), dan nomor dokumen `CANCELLED` tidak dipakai ulang.
* **Pagination & Keamanan Query (FR-11):** Menguji parameter `limit` (bawaan 50, maks 200), `offset`, filter rentang tanggal pada *ledger*, serta memastikan parameter `sort`/`order_by` di luar *whitelist* ditolak (mencegah SQL Injection pada `ORDER BY`).

---

## 5. Pengujian Non-Fungsional (Kinerja & Operasional)

1. **Kinerja Query Stok & Master Data (PRD 7.3):**
   * Pada tahap **M8 (Pengerasan)**, dilakukan pengujian beban baca dengan data uji representatif dan pemeriksaan rencana eksekusi query menggunakan `EXPLAIN ANALYZE`.
   * Target: pembacaan saldo stok dan pencarian master data berada di bawah **200 ms (p95)** dan memanfaatkan indeks komposit PostgreSQL (bukan *sequential scan* penuh pada tabel besar).
2. **Operasional & Observabilitas (PRD 7.6):**
   * `GET /api/v1/health` (atau `/health`) mengembalikan status kesehatan aplikasi dan konektivitas database.
   * Setiap respons menyertakan header `X-Request-ID` (baik diteruskan dari request klien maupun dibuat otomatis oleh `core/middleware.py`).
   * Setiap error bisnis mengembalikan struktur JSON standar Lampiran B PRD:
     ```json
     {
       "error": {
         "code": "INSUFFICIENT_STOCK",
         "message": "...",
         "details": {}
       }
     }
     ```
     tanpa membocorkan *stack trace* atau query SQL internal.

---

## 6. Matriks Pemetaan Tahap Implementasi ke Pengujian

Sesuai urutan kerja pada `docs/core/FOLDER_STRUCTURE.md` Bagian 9:

| Tahap | Fokus Implementasi | Pengujian yang Wajib Lulus |
| --- | --- | --- |
| **M0 Fondasi** | Kerangka proyek, pool DB, middleware `X-Request-ID`, `/health`, runner migrasi | Test `/health`, header `X-Request-ID`, dan eksekusi `python -m db.migrate` |
| **M1 Skema** | Migrasi `001`–`008` (tabel, FK komposit, `UNIQUE`, `CHECK`, *trigger* append-only, seed RBAC) | **AC-08** (`test_immutability.py`) dengan role `wms_app` |
| **M2 Auth & Audit** | Login, rotasi *refresh token*, `require_permission`, `audit_service`, `create_superadmin.py` | **AC-11**, **AC-05** (bagian RBAC & audit dasar) (`test_auth.py`, `test_rbac_scoping.py`) |
| **M3 Master & Scoping** | CRUD master data, aturan penonaktifan (`ENTITY_IN_USE`), `access_service` | **AC-12** (`test_rbac_scoping.py`) & pengujian validasi master data |
| **M4 Inti Stok** | `inventory_service.apply_movement`, `stock_service`, `numbering_service` | Pengujian penguncian `apply_movement` multi-thread & penomoran dokumen konkuren |
| **M5 PO & GR** | Siklus PO lengkap, pembuatan & posting GR atomik | **AC-01**, **AC-07**, **AC-13** (`test_goods_receipt.py`) |
| **M6 Transfer** | Alur `DRAFT → APPROVED → SHIPPED → RECEIVED`, selisih penerimaan | **AC-02**, **AC-03**, **AC-06**, **AC-09** (`test_stock_transfer.py`) |
| **M7 Opname** | *Snapshot* saldo, pembekuan lokasi, persetujuan/penolakan, penyesuaian stok | **AC-04**, **AC-10** (`test_stock_opname.py`) |
| **M8 Pengerasan** | Evaluasi akhir seluruh AC, `EXPLAIN ANALYZE` indeks stok & ledger, audit keamanan | Seluruh **AC-01 s.d. AC-13** hijau + verifikasi kinerja < 200 ms |

---

## 7. Perintah Eksekusi & Definisi Selesai (*Definition of Done*)

### 7.1. Perintah Menjalankan Pengujian

```bash
# Menjalankan migrasi pada database uji (bila belum otomatis di fixture)
python -m db.migrate

# Menjalankan seluruh suite pengujian
pytest

# Menjalankan pengujian dengan output detail
pytest -v

# Menjalankan satu Acceptance Criteria tertentu (contoh: AC-06)
pytest -k ac06

# Menjalankan satu berkas modul pengujian tertentu
pytest tests/test_stock_transfer.py
```

### 7.2. Checklist Definisi Selesai (DoD) QA
Sebuah fitur atau tahap implementasi baru dinyatakan **Selesai (Done)** apabila:
- [ ] Seluruh skenario positif dan negatif sesuai PRD serta mengembalikan HTTP status & kode error persis seperti katalog Lampiran B PRD.
- [ ] Pengujian otomatis untuk AC yang relevan telah ditulis dan **lulus (hijau)** saat dijalankan terhadap PostgreSQL sungguhan (`wms_test`).
- [ ] Invarian bisnis terjaga: tidak ada perubahan stok di luar `inventory_service.apply_movement()`, setiap mutasi memiliki pasangan `stock_movements` dan `audit_logs` dalam satu transaksi yang sama, dan kuantitas selalu menggunakan `Decimal` / string desimal.
- [ ] Pengujian konkurensi (**AC-06**, **AC-13**) terbukti bebas *race condition* dan bebas *deadlock* berkat urutan penguncian seragam.
- [ ] Pengujian imutabilitas (**AC-08**) terbukti menolak `UPDATE`/`DELETE`/`TRUNCATE` pada `stock_movements` dan `audit_logs` menggunakan role aplikasi `wms_app`.
### 2.3. Struktur Berkas Pengujian (`tests/`)

Sesuai `docs/core/FOLDER_STRUCTURE.md`, berkas pengujian disusun sebagai berikut:

| Berkas | Tanggung Jawab & Cakupan AC |
| --- | --- |
| `tests/conftest.py` | Setup database `wms_test`, eksekusi migrasi `001`–`008`, pembersihan tabel antar-test (`TRUNCATE ... RESTART IDENTITY CASCADE`), pembuatan *fixture* `client`, koneksi database, serta *fixture* pengguna beserta token untuk ke-5 peran (Super Admin, Warehouse Manager, Purchasing Staff, Warehouse Staff, Auditor). |
| `tests/factories.py` | Fungsi pembantu (*helper*) untuk menyiapkan data prasyarat secara cepat dan konsisten: gudang, lokasi penyimpanan, kategori, UoM, barang (item), pemasok, PO, maupun saldo stok awal. |
| `tests/test_auth.py` | Menguji siklus autentikasi, rotasi & pencabutan *Refresh Token*, deteksi *token reuse*, *logout*, dan penguncian akun (**AC-11**, FR-01). |
| `tests/test_rbac_scoping.py` | Menguji matriks *permission* untuk 5 peran, verifikasi status aktif/peran langsung dari DB setiap request, *warehouse scoping*, dan pencatatan *Audit Log* (**AC-05**, **AC-12**, FR-01, FR-09). |
| `tests/test_goods_receipt.py` | Menguji alur PO ke GR, penerimaan parsial & penuh, pencegahan *over-receipt*, atomisitas transaksi (*rollback* saat gagal di tengah), dan pencegahan posting GR ganda secara konkuren (**AC-01**, **AC-07**, **AC-13**, FR-04, FR-05). |
| `tests/test_stock_transfer.py` | Menguji alur Transfer Stok (`DRAFT` → `APPROVED` → `SHIPPED` → `RECEIVED`), pencegahan stok negatif, konsistensi stok *in-transit* & *ledger*, konkurensi pengiriman stok, dan aturan selisih penerimaan (**AC-02**, **AC-03**, **AC-06**, **AC-09**, FR-03, FR-06). |
| `tests/test_stock_opname.py` | Menguji siklus Stock Opname, pengambilan *snapshot* `qty_system`, pembekuan lokasi (*location freeze*), penambahan baris saldo awal (`qty_system = 0`), persetujuan/penolakan, dan rekonsiliasi saldo (**AC-04**, **AC-10**, FR-07). |
| `tests/test_immutability.py` | Menguji keabadian (*append-only*) tabel `stock_movements` dan `audit_logs` baik dari sisi izin role `wms_app` maupun *trigger* PostgreSQL (**AC-08**, FR-08, FR-09). |

---

## 3. Rincian Pengujian Kriteria Penerimaan (AC-01 s.d. AC-13)

Setiap Kriteria Penerimaan pada PRD Bagian 8 wajib memiliki minimal satu fungsi pengujian eksplisit yang memuat kode AC pada namanya.

### AC-01 — Penerimaan Parsial & Pemenuhan PO
* **Berkas:** `tests/test_goods_receipt.py`
* **Contoh Nama Test:** `test_ac01_partial_and_full_goods_receipt_fulfillment`
* **Prasyarat (*Given*):** PO berstatus `ISSUED` untuk 50 unit Barang X pada Gudang A.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Posting GR #1 sebesar `20.0000` unit → HTTP 200; status PO berubah menjadi `PARTIALLY_RECEIVED`; `po_lines.qty_received = 20.0000`; `inventory_balances.qty_on_hand = 20.0000`; tercatat 1 baris `stock_movements` bertipe `IN_PURCHASE` (`+20.0000`).
  2. Buat & coba posting GR #2 sebesar `35.0000` unit → Ditolak dengan **HTTP 409** dan kode error `OVER_RECEIPT` (karena `20 + 35 = 55 > 50`). Saldo stok tetap `20.0000` dan status PO tetap `PARTIALLY_RECEIVED`.
  3. Ubah/buat GR #2 sebesar `30.0000` unit lalu posting → HTTP 200; `po_lines.qty_received = 50.0000`; status PO otomatis menjadi `RECEIVED`; saldo stok menjadi `50.0000`.

### AC-02 — Pencegahan Stok Negatif
* **Berkas:** `tests/test_stock_transfer.py`
* **Contoh Nama Test:** `test_ac02_negative_stock_prevention_on_transfer_ship`
* **Prasyarat (*Given*):** Saldo Barang Y di Gudang A (Lokasi A1) = `10.0000` unit; Gudang A memiliki `allow_negative_stock = FALSE`; dokumen Transfer 12 unit dari Gudang A (Lokasi A1) ke Gudang B berstatus `APPROVED`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Eksekusi `POST /api/v1/stock-transfers/{id}/ship` → Ditolak dengan **HTTP 409** (`INSUFFICIENT_STOCK`) beserta detail barang, stok tersedia (`10.0000`), dan kuantitas diminta (`12.0000`).
  2. Verifikasi database: saldo di Lokasi A1 tetap `10.0000`, status Transfer tetap `APPROVED`, dan tidak ada baris `OUT_TRANSFER` baru di `stock_movements`.

### AC-03 — Konsistensi Transfer Antar-Gudang
* **Berkas:** `tests/test_stock_transfer.py`
* **Contoh Nama Test:** `test_ac03_inter_warehouse_transfer_consistency`
* **Prasyarat (*Given*):** Saldo awal Gudang A (Lokasi A1) = `50.0000`, Gudang B (Lokasi B1) = `0.0000`. Transfer 15 unit dari A1 ke B1 berstatus `APPROVED`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Eksekusi `POST /api/v1/stock-transfers/{id}/ship` → HTTP 200; status menjadi `SHIPPED`; stok Lokasi A1 berkurang menjadi `35.0000`; tercatat 1 baris `OUT_TRANSFER` (`qty_before=50`, `qty_change=-15`, `qty_after=35`); stok Lokasi B1 masih `0.0000`; endpoint stok menampilkan `in_transit = 15.0000`.
  2. Eksekusi `POST /api/v1/stock-transfers/{id}/receive` dengan `qty_received = "15.0000"` → HTTP 200; status menjadi `RECEIVED`; stok Lokasi B1 bertambah menjadi `15.0000`; tercatat 1 baris `IN_TRANSFER` (`qty_before=0`, `qty_change=+15`, `qty_after=15`); `in_transit` kembali `0.0000`.

### AC-04 — Rekonsiliasi Stock Opname
* **Berkas:** `tests/test_stock_opname.py`
* **Contoh Nama Test:** `test_ac04_stock_opname_reconciliation_adjustment_minus`
* **Prasyarat (*Given*):** Saldo Barang Z di Lokasi A1 tercatat `100.0000` unit. Sesi Opname dimulai (`IN_PROGRESS` → mengambil `qty_system = 100.0000`), petugas menginput `qty_physical = "97.0000"` dan mengajukan persetujuan (`WAITING_APPROVAL`).
* **Langkah & Ekspektasi (*When / Then*):**
  1. *Warehouse Manager* menyetujui opname (`POST /api/v1/stock-opnames/{id}/approve`) → HTTP 200; status Opname menjadi `COMPLETED`.
  2. Baris opname mencatat `qty_variance = "-3.0000"`.
  3. Saldo di `inventory_balances` diperbarui menjadi `97.0000`.
  4. Tercatat 1 baris `stock_movements` dengan `movement_type = 'ADJUSTMENT_MINUS'`, `qty_before = 100.0000`, `qty_change = -3.0000`, `qty_after = 97.0000`, `reference_type = 'STOCK_OPNAME'`.

### AC-05 — Kepatuhan RBAC & Audit Log
* **Berkas:** `tests/test_rbac_scoping.py`
* **Contoh Nama Test:** `test_ac05_rbac_enforcement_and_audit_log_recording`
* **Prasyarat (*Given*):** Pengguna dengan peran *Warehouse Staff* dan pengguna dengan peran *Purchasing Staff* / *Warehouse Manager*.
* **Langkah & Ekspektasi (*When / Then*):**
  1. *Warehouse Staff* mencoba menerbitkan PO (`POST /purchase-orders/{id}/issue`) atau menyetujui akhir Stock Opname (`POST /stock-opnames/{id}/approve`) → Ditolak dengan **HTTP 403** (`PERMISSION_DENIED`).
  2. Pengguna berwenang melakukan perubahan data yang sah (misalnya menerbitkan PO atau mengubah master barang) → HTTP 200; otomatis tercipta 1 baris baru di tabel `audit_logs` yang memuat `user_id`, `action`, `entity_type`, `entity_id`, `old_values`, `new_values`, `ip_address`, dan `created_at`.

### AC-06 — Konkurensi Pengiriman
* **Berkas:** `tests/test_stock_transfer.py`
* **Contoh Nama Test:** `test_ac06_concurrent_ship_only_one_succeeds`
* **Prasyarat (*Given*):** Saldo Barang Y di Lokasi A1 = `10.0000` unit (`allow_negative_stock = FALSE`). Dua dokumen Transfer berbeda (TRF-1 dan TRF-2) masing-masing meminta `8.0000` unit dari Lokasi A1, keduanya berstatus `APPROVED`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Dua *worker thread* disinkronkan dengan `threading.Barrier(2)` untuk memanggil `POST /stock-transfers/{id1}/ship` dan `POST /stock-transfers/{id2}/ship` secara bersamaan melalui koneksi database terpisah.
  2. Tepat **satu** request menghasilkan HTTP 200 (`SHIPPED`), dan **satu** request ditolak dengan **HTTP 409** (`INSUFFICIENT_STOCK`).
  3. Saldo akhir di Lokasi A1 adalah `2.0000` unit, dan hanya ada **1 baris** `OUT_TRANSFER` sebesar `-8.0000` pada `stock_movements`.

### AC-07 — Atomisitas Transaksi
* **Berkas:** `tests/test_goods_receipt.py`
* **Contoh Nama Test:** `test_ac07_transaction_atomicity_rollback_on_failure`
* **Prasyarat (*Given*):** Sebuah GR berstatus `DRAFT` untuk PO yang `ISSUED`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Simulasikan kegagalan di tengah eksekusi `post_goods_receipt` setelah perubahan stok tetapi sebelum transaksi selesai (misalnya dengan menyuntikkan kegagalan pada pemanggilan `audit_repo` / `audit_service.record` atau *ledger*).
  2. Permintaan gagal dan seluruh transaksi di-*rollback*.
  3. Verifikasi database: status GR tetap `DRAFT`, `inventory_balances.qty_on_hand` tidak bertambah, `po_lines.qty_received` tidak berubah, serta tidak ada baris baru yang tertinggal di `stock_movements` maupun `audit_logs`.

### AC-08 — Imutabilitas Buku Besar & Audit Log
* **Berkas:** `tests/test_immutability.py`
* **Contoh Nama Test:** `test_ac08_stock_movements_and_audit_logs_are_immutable`
* **Prasyarat (*Given*):** Terdapat baris data pada tabel `stock_movements` dan `audit_logs`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Menggunakan koneksi langsung ber-role `wms_app` (dan diuji pula terhadap *trigger* database), jalankan perintah SQL `UPDATE stock_movements SET qty_change = 999 WHERE id = ...` dan `DELETE FROM stock_movements WHERE id = ...`.
  2. Lakukan hal yang sama untuk `UPDATE audit_logs ...` dan `DELETE FROM audit_logs ...`.
  3. Seluruh operasi `UPDATE`, `DELETE`, maupun `TRUNCATE` ditolak oleh PostgreSQL (error *permission denied* atau *exception* dari *trigger* imutabilitas), dan isi kedua tabel tetap utuh tanpa perubahan.

### AC-09 — Selisih Penerimaan Transfer
* **Berkas:** `tests/test_stock_transfer.py`
* **Contoh Nama Test:** `test_ac09_transfer_receive_variance_validation_and_recording`
* **Prasyarat (*Given*):** Transfer 25 unit berstatus `SHIPPED` dari Gudang A ke Gudang B.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Terima Transfer dengan `qty_received = "26.0000"` → Ditolak **HTTP 409** (`TRANSFER_QTY_EXCEEDS_SHIPPED`).
  2. Terima Transfer dengan `qty_received = "23.0000"` tanpa `variance_reason` (kosong/null) → Ditolak **HTTP 422** (`VALIDATION_ERROR`).
  3. Terima Transfer dengan `qty_received = "23.0000"` dan `variance_reason = "2 unit rusak saat pengiriman"` → HTTP 200 (`RECEIVED`).
  4. Stok tujuan bertambah `23.0000` unit, tercatat 1 baris `IN_TRANSFER` sebesar `+23.0000` (tidak ada baris ledger untuk selisih 2 unit, dan stok asal tidak dikembalikan), serta baris Transfer menyimpan `qty_received = 23.0000` beserta alasan selisihnya.

### AC-10 — Pembekuan Lokasi Opname
* **Berkas:** `tests/test_stock_opname.py`
* **Contoh Nama Test:** `test_ac10_location_frozen_during_active_opname`
* **Prasyarat (*Given*):** Sesi Opname pada Lokasi X dimulai sehingga berstatus `IN_PROGRESS` (dan juga diuji saat `WAITING_APPROVAL`).
* **Langkah & Ekspektasi (*When / Then*):**
  1. Coba posting GR yang memasukkan barang ke Lokasi X → Ditolak **HTTP 409** (`LOCATION_FROZEN`).
  2. Coba kirim Transfer (`ship`) dari Lokasi X atau terima Transfer (`receive`) ke Lokasi X → Ditolak **HTTP 409** (`LOCATION_FROZEN`).
  3. Selesaikan Opname (`COMPLETED`) atau batalkan (`CANCELLED`) → Pembekuan lokasi lepas; posting GR dan pengiriman/penerimaan Transfer pada Lokasi X kini berhasil (HTTP 200).

### AC-11 — Siklus Refresh Token & Deteksi Pencurian
* **Berkas:** `tests/test_auth.py`
* **Contoh Nama Test:** `test_ac11_refresh_token_rotation_reuse_detection_and_logout`
* **Prasyarat (*Given*):** Pengguna berhasil login dan memperoleh *Refresh Token* `R1`.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Gunakan `R1` pada `POST /api/v1/auth/refresh` → HTTP 200; terbit *Access Token* baru dan *Refresh Token* `R2`; status `R1` di database tercatat `revoked_at IS NOT NULL` dan `replaced_by_id` menunjuk ke `R2`.
  2. Gunakan kembali `R1` yang sudah dicabut pada `POST /api/v1/auth/refresh` → Ditolak **HTTP 401** (`AUTH_TOKEN_INVALID`); sistem mendeteksi penyalahgunaan token dan otomatis mencabut **seluruh** *Refresh Token* aktif milik pengguna tersebut (termasuk `R2`), serta mencatat insiden pada `audit_logs`.
  3. Coba gunakan `R2` setelah pencabutan massal → Ditolak **HTTP 401**.
  4. Login ulang untuk mendapat `R3`, lalu panggil `POST /api/v1/auth/logout` dengan `R3` → `R3` dicabut dan tidak bisa dipakai lagi untuk `refresh` (**HTTP 401**).

### AC-12 — Warehouse Scoping
* **Berkas:** `tests/test_rbac_scoping.py`
* **Contoh Nama Test:** `test_ac12_warehouse_scoping_blocks_unassigned_warehouse`
* **Prasyarat (*Given*):** Pengguna *Warehouse Staff* yang hanya ditugaskan pada **Gudang A** di tabel `user_warehouses`. Terdapat PO yang ditujukan ke **Gudang B**.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Pengguna tersebut mencoba membuat atau memposting GR untuk PO Gudang B → Ditolak **HTTP 403** dengan kode `WAREHOUSE_NOT_ASSIGNED`.
  2. Diuji juga untuk aksi bertanda **(g)** lainnya pada Matriks 3.1: `location:manage`, `transfer:create/approve/ship` (wajib ditugaskan di gudang asal), `transfer:receive` (wajib ditugaskan di gudang tujuan), `opname:manage/count/approve`, serta pembatasan pembacaan data bagi *Warehouse Staff*.

### AC-13 — Pencegahan Posting Ganda
* **Berkas:** `tests/test_goods_receipt.py`
* **Contoh Nama Test:** `test_ac13_concurrent_double_post_goods_receipt_prevented`
* **Prasyarat (*Given*):** Sebuah GR berstatus `DRAFT` sebesar `10.0000` unit.
* **Langkah & Ekspektasi (*When / Then*):**
  1. Dua permintaan `POST /api/v1/goods-receipts/{id}/post` untuk ID GR yang sama dikirim secara bersamaan menggunakan 2 *thread* yang disinkronkan lewat `threading.Barrier(2)`.
  2. Karena baris header GR dikunci (`SELECT ... FOR UPDATE`) sebelum pemeriksaan status, tepat **satu** permintaan berhasil (HTTP 200, status `POSTED`) dan permintaan lainnya ditolak dengan **HTTP 409** (`INVALID_STATE_TRANSITION`).
  3. Saldo stok di gudang tujuan hanya bertambah `10.0000` unit (bukan 20), `po_lines.qty_received` hanya bertambah `10.0000`, dan hanya tercipta 1 baris `IN_PURCHASE` di `stock_movements`.

---

## 4. Cakupan Pengujian Fungsional & Aturan Bisnis Tambahan

Selain ke-13 AC utama di atas, suite pengujian juga mencakup validasi per modul sesuai FR-01 s.d. FR-11 dan Bab 6 PRD:

### 4.1. Keamanan & Autentikasi Tambahan (FR-01, Bab 6.4, 7.2)
* **Penguncian Akun (*Account Lockout*):** Gagal login 5 kali berturut-turut mengunci akun selama 15 menit; percobaan login berikutnya (meski password benar) ditolak dengan **HTTP 429** (`AUTH_TOO_MANY_ATTEMPTS`). Setiap gagal login tercatat di `audit_logs`.
* **Verifikasi Peran & Status Aktif per Request:** Jika pengguna sedang memegang *Access Token* yang belum kedaluwarsa lalu Super Admin menonaktifkan akun tersebut (`is_active = FALSE`) atau mengubah perannya di DB, request berikutnya langsung ditolak tanpa menunggu token 15 menit habis.
* **Kerahasiaan di Audit Log:** Memastikan perubahan pengguna, login, atau ganti password tidak pernah membocorkan `password`, `password_hash`, maupun token ke kolom `old_values`/`new_values` di `audit_logs`.

### 4.2. Master Data & Aturan Penonaktifan (FR-02, Bab 6.3, 6.8, 6.9)
* **Larangan Hard Delete:** Memastikan tidak ada endpoint `DELETE` permanen; penonaktifan menggunakan `is_active = FALSE`.
* **Perlindungan Entitas Sedang Dipakai (`ENTITY_IN_USE` - HTTP 409):**
  * Menolak penonaktifan gudang, lokasi, atau barang yang masih memiliki `qty_on_hand != 0` atau masih tercantum pada dokumen belum final (`DRAFT`, `ISSUED`, `PARTIALLY_RECEIVED`, `APPROVED`, `SHIPPED`, `IN_PROGRESS`, `WAITING_APPROVAL`).
  * Menolak penonaktifan pemasok yang masih memiliki PO belum final.
* **Imutabilitas SKU:** Mengubah `sku` barang yang sudah pernah dipakai di transaksi ditolak.
* **Aturan Desimal UoM (`allow_decimal`):** Jika barang memiliki UoM dengan `allow_decimal = FALSE`, input kuantitas pecahan (mis. `"5.2500"`) pada PO/GR/Transfer/Opname ditolak dengan **HTTP 422** (`VALIDATION_ERROR`).
* **Validasi Referensi & Lokasi:**
  * Memilih lokasi yang bukan milik gudang terkait atau tidak aktif → **HTTP 422** (`INVALID_LOCATION`).
  * Membuat dokumen dengan barang/gudang/pemasok nonaktif → **HTTP 422** (`INACTIVE_REFERENCE`).
  * Transfer dengan `(source_warehouse_id, source_location_id)` sama dengan tujuan → ditolak **HTTP 422**.
  * Duplikasi kode unik (SKU, kode gudang, kode lokasi dalam gudang yang sama, barang ganda dalam satu PO) → **HTTP 409** (`DUPLICATE`) atau **HTTP 422**.

### 4.3. Siklus Status Dokumen (Bab 5.1)
* Memastikan seluruh perubahan status hanya bisa melalui endpoint aksi (`/{id}/issue`, `/cancel`, `/close`, `/post`, `/approve`, `/ship`, `/receive`, `/start`, `/submit`, `/reject`).
* Menguji transisi tidak sah (misalnya membatalkan PO `ISSUED` yang sudah punya GR `POSTED`/`DRAFT`, menutup PO `ISSUED` tanpa alasan penutupan atau saat masih ada GR `DRAFT`, menolak Opname tanpa `rejection_reason`) → ditolak dengan **HTTP 409** (`INVALID_STATE_TRANSITION`) atau **HTTP 422** (`VALIDATION_ERROR`).

### 4.4. Saldo Awal, In-Transit, Presisi Numerik & Invarian Ledger (FR-03, FR-08, FR-10, FR-11)
* **Input Saldo Awal lewat Opname:** Menguji penambahan baris barang yang belum punya saldo (`qty_system = 0`) pada sesi Opname, diisi `qty_physical > 0`, lalu disetujui → menghasilkan `ADJUSTMENT_PLUS` dan membuat saldo awal.
* **Opsi `allow_negative_stock = TRUE`:** Menguji bahwa bila Super Admin mengaktifkan `allow_negative_stock = TRUE` pada suatu gudang, pengiriman Transfer diizinkan melewati 0 dan mencatat `qty_after` negatif di `stock_movements`.
* **Invarian Buku Besar:** Setelah rangkaian transaksi (GR, Transfer, Opname), memverifikasi bahwa untuk setiap `(warehouse_id, location_id, item_id)`:
  * Setiap baris memenuhi `qty_after = qty_before + qty_change`.
  * `qty_after` pada baris `stock_movements` terakhir persis sama dengan `inventory_balances.qty_on_hand`.
* **Presisi Kuantitas:** Memastikan seluruh respons JSON menyajikan kuantitas sebagai **string desimal** (contoh `"10.0000"`), bukan `float`.
* **Penomoran Dokumen (FR-10):** Memastikan nomor dokumen mengikuti format `{PREFIX}-{YYYYMM}-{NNNN}` (`PO`, `GR`, `TRF`, `OPN`), urut, aman saat dibuat bersamaan (konkuren), dan nomor dokumen `CANCELLED` tidak dipakai ulang.
* **Pagination & Keamanan Query (FR-11):** Menguji parameter `limit` (bawaan 50, maks 200), `offset`, filter rentang tanggal pada *ledger*, serta memastikan parameter `sort`/`order_by` di luar *whitelist* ditolak (mencegah SQL Injection pada `ORDER BY`).

---

## 5. Pengujian Non-Fungsional (Kinerja & Operasional)

1. **Kinerja Query Stok & Master Data (PRD 7.3):**
   * Pada tahap **M8 (Pengerasan)**, dilakukan pengujian beban baca dengan data uji representatif dan pemeriksaan rencana eksekusi query menggunakan `EXPLAIN ANALYZE`.
   * Target: pembacaan saldo stok dan pencarian master data berada di bawah **200 ms (p95)** dan memanfaatkan indeks komposit PostgreSQL (bukan *sequential scan* penuh pada tabel besar).
2. **Operasional & Observabilitas (PRD 7.6):**
   * `GET /api/v1/health` (atau `/health`) mengembalikan status kesehatan aplikasi dan konektivitas database.
   * Setiap respons menyertakan header `X-Request-ID` (baik diteruskan dari request klien maupun dibuat otomatis oleh `core/middleware.py`).
   * Setiap error bisnis mengembalikan struktur JSON standar Lampiran B PRD:
     ```json
     {
       "error": {
         "code": "INSUFFICIENT_STOCK",
         "message": "...",
         "details": {}
       }
     }
     ```
     tanpa membocorkan *stack trace* atau query SQL internal.

---

## 6. Matriks Pemetaan Tahap Implementasi ke Pengujian

Sesuai urutan kerja pada `docs/core/FOLDER_STRUCTURE.md` Bagian 9:

| Tahap | Fokus Implementasi | Pengujian yang Wajib Lulus |
| --- | --- | --- |
| **M0 Fondasi** | Kerangka proyek, pool DB, middleware `X-Request-ID`, `/health`, runner migrasi | Test `/health`, header `X-Request-ID`, dan eksekusi `python -m db.migrate` |
| **M1 Skema** | Migrasi `001`–`008` (tabel, FK komposit, `UNIQUE`, `CHECK`, *trigger* append-only, seed RBAC) | **AC-08** (`test_immutability.py`) dengan role `wms_app` |
| **M2 Auth & Audit** | Login, rotasi *refresh token*, `require_permission`, `audit_service`, `create_superadmin.py` | **AC-11**, **AC-05** (bagian RBAC & audit dasar) (`test_auth.py`, `test_rbac_scoping.py`) |
| **M3 Master & Scoping** | CRUD master data, aturan penonaktifan (`ENTITY_IN_USE`), `access_service` | **AC-12** (`test_rbac_scoping.py`) & pengujian validasi master data |
| **M4 Inti Stok** | `inventory_service.apply_movement`, `stock_service`, `numbering_service` | Pengujian penguncian `apply_movement` multi-thread & penomoran dokumen konkuren |
| **M5 PO & GR** | Siklus PO lengkap, pembuatan & posting GR atomik | **AC-01**, **AC-07**, **AC-13** (`test_goods_receipt.py`) |
| **M6 Transfer** | Alur `DRAFT → APPROVED → SHIPPED → RECEIVED`, selisih penerimaan | **AC-02**, **AC-03**, **AC-06**, **AC-09** (`test_stock_transfer.py`) |
| **M7 Opname** | *Snapshot* saldo, pembekuan lokasi, persetujuan/penolakan, penyesuaian stok | **AC-04**, **AC-10** (`test_stock_opname.py`) |
| **M8 Pengerasan** | Evaluasi akhir seluruh AC, `EXPLAIN ANALYZE` indeks stok & ledger, audit keamanan | Seluruh **AC-01 s.d. AC-13** hijau + verifikasi kinerja < 200 ms |

---

## 7. Perintah Eksekusi & Definisi Selesai (*Definition of Done*)

### 7.1. Perintah Menjalankan Pengujian

```bash
# Menjalankan migrasi pada database uji (bila belum otomatis di fixture)
python -m db.migrate

# Menjalankan seluruh suite pengujian
pytest

# Menjalankan pengujian dengan output detail
pytest -v

# Menjalankan satu Acceptance Criteria tertentu (contoh: AC-06)
pytest -k ac06

# Menjalankan satu berkas modul pengujian tertentu
pytest tests/test_stock_transfer.py
```

### 7.2. Checklist Definisi Selesai (DoD) QA
Sebuah fitur atau tahap implementasi baru dinyatakan **Selesai (Done)** apabila:
- [ ] Seluruh skenario positif dan negatif sesuai PRD serta mengembalikan HTTP status & kode error persis seperti katalog Lampiran B PRD.
- [ ] Pengujian otomatis untuk AC yang relevan telah ditulis dan **lulus (hijau)** saat dijalankan terhadap PostgreSQL sungguhan (`wms_test`).
- [ ] Invarian bisnis terjaga: tidak ada perubahan stok di luar `inventory_service.apply_movement()`, setiap mutasi memiliki pasangan `stock_movements` dan `audit_logs` dalam satu transaksi yang sama, dan kuantitas selalu menggunakan `Decimal` / string desimal.
- [ ] Pengujian konkurensi (**AC-06**, **AC-13**) terbukti bebas *race condition* dan bebas *deadlock* berkat urutan penguncian seragam.
- [ ] Pengujian imutabilitas (**AC-08**) terbukti menolak `UPDATE`/`DELETE`/`TRUNCATE` pada `stock_movements` dan `audit_logs` menggunakan role aplikasi `wms_app`.
