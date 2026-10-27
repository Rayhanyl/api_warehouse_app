# Product Requirements Document (PRD) — Sistem Manajemen Gudang (WMS)

| | |
| --- | --- |
| **Versi** | 2.0 (revisi dari v1) |
| **Status** | Acuan implementasi MVP |
| **Bentuk produk** | Service REST API (tanpa antarmuka pengguna) |
| **Teknologi inti** | Python, FastAPI, PostgreSQL (akses langsung lewat driver, tanpa ORM), JWT |
| **Dokumen pendamping** | `FOLDER_STRUCTURE.md` (struktur folder & arsitektur kode) |

---

## 1. Tujuan Sistem

Sistem Manajemen Gudang (*Warehouse Management System* / WMS) berbasis Python dan FastAPI ini dirancang untuk menyediakan kontrol operasional yang akurat, *real-time*, dan dapat diaudit atas persediaan fisik barang di berbagai lokasi gudang. Sistem berbentuk service REST API; konsumennya adalah klien API (Swagger UI bawaan FastAPI, Postman, atau frontend yang dibangun terpisah). Tujuan utama sistem meliputi:

* **Sentralisasi Visibilitas Multi-Gudang:** Memantau ketersediaan stok secara terpisah maupun agregat di setiap gudang dan lokasi penyimpanan (*bin/rack*), termasuk stok dalam perjalanan (*in-transit*).
* **Akurasi Siklus Pengadaan & Penerimaan:** Memastikan setiap penerimaan barang (*Goods Receipt*) tervalidasi terhadap pesanan pembelian (*Purchase Order*), termasuk penanganan pengiriman bertahap (parsial).
* **Ketertelusuran Penuh (*Full Traceability*):** Mencatat setiap mutasi barang melalui buku besar pergerakan stok (*Stock Movement Ledger*) yang bersifat *append-only* (tidak dapat diubah/dihapus) serta melacak aktivitas pengguna melalui *Audit Log*.
* **Integritas Data Persediaan:** Mencegah selisih stok tidak sah dan menghindari stok negatif melalui validasi transaksi yang ketat serta rekonsiliasi fisik berkala (*Stock Opname*).

---

## 2. Ruang Lingkup Sistem (*System Scope*)

### 2.1. Fitur dalam Ruang Lingkup (*In-Scope*)

1. **Manajemen Master Data:** Kategori, satuan ukur (*Unit of Measure* / UoM), barang (*item*), pemasok (*supplier*), gudang (*warehouse*), dan lokasi penyimpanan (*storage location/bin*).
2. **Manajemen Multi-Gudang & Stok:** Saldo stok aktual per barang pada tingkat gudang dan lokasi penyimpanan, serta tampilan stok dalam perjalanan.
3. **Purchase Order (PO):** Pembuatan, penerbitan (*issue*), pembatalan, penutupan, dan pemantauan status pemenuhan pesanan pembelian ke pemasok.
4. **Penerimaan Barang (*Goods Receipt*):** Pencatatan barang masuk berdasarkan referensi PO, mendukung penerimaan parsial maupun penuh.
5. **Transfer Stok Antar-Gudang/Lokasi:** Proses pemindahan barang dengan persetujuan *Warehouse Manager* dan dua tahapan fisik eksplisit (pengiriman dari asal dan penerimaan di tujuan) untuk mengontrol stok *in-transit*.
6. **Stock Opname:** Pencatatan hasil hitung fisik, komparasi otomatis dengan stok sistem, pembekuan lokasi selama penghitungan, serta pembuatan penyesuaian stok (*stock adjustment*) setelah disetujui. Stock Opname juga menjadi mekanisme input **saldo awal** stok.
7. **Buku Besar Pergerakan Stok (*Stock Movement Ledger*):** Pencatatan kronologis atas seluruh transaksi penambah dan pengurang stok.
8. **Audit Log:** Pencatatan jejak audit perubahan data penting (siapa, kapan, aksi apa, nilai sebelum, dan nilai sesudah).
9. **Autentikasi, Otorisasi, Manajemen Pengguna & Menu Navigasi:** Pengamanan akses berbasis JWT (*Access Token* & *Refresh Token*), *Role-Based Access Control* (RBAC), penugasan pengguna ke gudang (*Warehouse Scoping*), serta penyediaan struktur menu navigasi dinamis dari database (`menus`) berbasis *permission* agar klien *frontend* cukup merender menu yang diizinkan.

### 2.2. Batasan & Fitur di Luar Ruang Lingkup (*Out of Scope*)

Untuk menjaga fokus pengembangan tahap awal (MVP), fitur berikut **dinyatakan secara eksplisit di luar ruang lingkup** dan tidak diimplementasikan:

* **Lot/Batch Tracking:** Sistem tidak melacak barang berdasarkan nomor *lot*, *batch* produksi, maupun tanggal kedaluwarsa (*expiry date*). Seluruh unit untuk SKU yang sama diperlakukan homogen.
* **Serial Number Tracking:** Sistem tidak melacak identitas unik per unit barang.
* **Inventory Costing:** Sistem hanya mengelola kuantitas fisik dan tidak menghitung valuasi persediaan maupun harga pokok (tidak ada FIFO, LIFO, FEFO, atau *Weighted Average Cost*).
* **Stock Reservation:** Tidak ada penguncian/alokasi stok semu (*soft allocation* / *reserved stock*); stok hanya berkurang saat transaksi pengeluaran fisik (pengiriman Transfer Stok atau penyesuaian Stock Opname) dieksekusi.
* **Goods Issue (Pengeluaran Barang):** Pengeluaran barang ke pelanggan, produksi, atau pemakaian internal belum ada. Pada MVP stok hanya berkurang lewat Transfer Stok (`SHIPPED`) dan penyesuaian Stock Opname negatif. Goods Issue direkomendasikan sebagai fase berikutnya.
* **Retur & Pembalikan Dokumen:** Tidak ada retur ke pemasok maupun pembalikan (*reversal*) GR yang sudah `POSTED`. Koreksi atas kesalahan penerimaan dilakukan melalui Stock Opname.
* **Konversi Satuan (UoM Conversion):** Setiap barang memiliki satu UoM dasar; seluruh PO, GR, Transfer, dan Opname memakai UoM tersebut.
* **Penerimaan Transfer Bertahap:** Penerimaan Transfer Stok dilakukan satu kali (final) per dokumen.
* **Persetujuan PO Multi-Level:** Penerbitan PO tidak memerlukan alur persetujuan berjenjang; penerbitan oleh pengguna berwenang dianggap sebagai persetujuan.
* **Antarmuka Pengguna & Integrasi Eksternal:** Tidak ada UI/frontend yang dibangun dalam MVP, notifikasi (email/WhatsApp), maupun integrasi ERP/barcode. Metadata navigasi untuk dikonsumsi frontend disediakan melalui API dan bukan merupakan UI.

---

## 3. Aktor dan Hak Akses (RBAC)

Sistem menerapkan pembatasan akses berbasis peran (*Role-Based Access Control*) serta cakupan akses gudang (*Warehouse Scoping*) bagi staf operasional.

| Peran (*Role*) | Deskripsi | Hak Akses Utama |
| --- | --- | --- |
| **Super Admin** | Administrator sistem TI | Akses penuh ke seluruh modul dan seluruh gudang (tidak dibatasi penugasan gudang): manajemen pengguna, *role/permission*, penugasan gudang, konfigurasi gudang (termasuk `allow_negative_stock`), dan pembacaan *Audit Log*. |
| **Warehouse Manager** | Kepala operasional gudang | Mengelola master lokasi pada gudang yang ditugaskan, menyetujui Transfer Stok, membuat/memulai/menyetujui Stock Opname, menutup PO, serta memantau seluruh laporan stok dan pergerakan barang di semua gudang. |
| **Purchasing Staff** | Staf pengadaan / pembelian | Mengelola master data pemasok, barang, kategori, dan UoM; membuat, merevisi (saat `DRAFT`), menerbitkan, membatalkan, dan menutup PO; melihat saldo stok. |
| **Warehouse Staff** | Operator operasional gudang | Membuat dan memposting *Goods Receipt* (berdasarkan PO aktif), membuat Transfer Stok serta mengeksekusi pengiriman dan penerimaannya, dan menginput hasil hitung fisik Stock Opname — seluruhnya hanya pada gudang yang ditugaskan. |
| **Auditor / Viewer** | Pemeriksa internal / manajemen | Akses *read-only* ke seluruh master data, saldo stok, *Stock Movement Ledger*, dokumen transaksi, hasil Stock Opname, dan *Audit Log*. |

### 3.1. Matriks Permission

Kode permission di bawah ini dipakai langsung sebagai identitas izin pada sistem (tabel `permissions`). Tanda **✓ (g)** berarti hanya berlaku pada gudang yang ditugaskan ke pengguna tersebut (lihat 3.2).

| Permission | Keterangan | Super Admin | Warehouse Manager | Purchasing Staff | Warehouse Staff | Auditor |
| --- | --- | :---: | :---: | :---: | :---: | :---: |
| `user:manage` | Kelola pengguna, role/permission, penugasan gudang, dan struktur menu | ✓ | – | – | – | – |
| `warehouse:manage` | Kelola gudang & konfigurasinya | ✓ | – | – | – | – |
| `location:manage` | Kelola lokasi penyimpanan | ✓ | ✓ (g) | – | – | – |
| `master:manage` | Kelola kategori, UoM, barang, pemasok | ✓ | – | ✓ | – | – |
| `master:read` | Baca master data | ✓ | ✓ | ✓ | ✓ | ✓ |
| `po:create` | Buat/ubah PO `DRAFT`, batalkan PO `DRAFT` | ✓ | – | ✓ | – | – |
| `po:issue` | Terbitkan PO | ✓ | – | ✓ | – | – |
| `po:cancel` | Batalkan PO `ISSUED` | ✓ | – | ✓ | – | – |
| `po:close` | Tutup PO | ✓ | ✓ | ✓ | – | – |
| `po:read` | Baca PO | ✓ | ✓ | ✓ | ✓ | ✓ |
| `gr:manage` | Buat, ubah, posting, batalkan GR | ✓ | – | – | ✓ (g) | – |
| `gr:read` | Baca GR | ✓ | ✓ | ✓ | ✓ (g) | ✓ |
| `transfer:create` | Buat/ubah/batalkan Transfer `DRAFT` | ✓ | – | – | ✓ (g) | – |
| `transfer:approve` | Setujui / batalkan Transfer | ✓ | ✓ (g) | – | – | – |
| `transfer:ship` | Kirim Transfer (`SHIPPED`) | ✓ | – | – | ✓ (g) | – |
| `transfer:receive` | Terima Transfer (`RECEIVED`) | ✓ | – | – | ✓ (g) | – |
| `transfer:read` | Baca Transfer | ✓ | ✓ | – | ✓ (g) | ✓ |
| `opname:manage` | Buat, mulai, batalkan sesi Opname | ✓ | ✓ (g) | – | – | – |
| `opname:count` | Input hitung fisik & ajukan persetujuan | ✓ | – | – | ✓ (g) | – |
| `opname:approve` | Setujui / tolak hasil Opname | ✓ | ✓ (g) | – | – | – |
| `opname:read` | Baca Opname | ✓ | ✓ | – | ✓ (g) | ✓ |
| `stock:read` | Baca saldo stok | ✓ | ✓ | ✓ | ✓ (g) | ✓ |
| `ledger:read` | Baca Stock Movement Ledger | ✓ | ✓ | – | ✓ (g) | ✓ |
| `audit:read` | Baca Audit Log | ✓ | – | – | – | ✓ |

Setiap pengguna terautentikasi dapat melihat profil sendiri, mengambil pohon menu navigasi sesuai hak aksesnya (`GET /menus/my-menu`), dan mengganti kata sandinya sendiri tanpa permission khusus.

### 3.2. Aturan Penugasan Gudang (*Warehouse Scoping*)

1. Penugasan pengguna ke gudang disimpan pada relasi `user_warehouses` dan hanya dapat diubah oleh Super Admin (`user:manage`).
2. Aksi bertanda **(g)** hanya boleh dilakukan pada gudang yang ditugaskan; pelanggaran ditolak dengan HTTP 403 dan kode `WAREHOUSE_NOT_ASSIGNED`.
3. Pada Transfer Stok: `transfer:ship` dan `transfer:approve` mensyaratkan penugasan pada **gudang asal**; `transfer:receive` mensyaratkan penugasan pada **gudang tujuan**; `transfer:create` mensyaratkan penugasan pada gudang asal.
4. Pada GR, gudang tujuan (gudang yang tercantum pada PO) harus termasuk gudang yang ditugaskan.
5. Untuk pembacaan, pengguna berperan *Warehouse Staff* hanya melihat dokumen dan stok pada gudang yang ditugaskan; Transfer terlihat bila pengguna ditugaskan pada gudang asal **atau** tujuan.
6. Super Admin, Warehouse Manager (untuk pembacaan), Purchasing Staff (hanya `stock:read` dan baca dokumen), dan Auditor tidak dibatasi penugasan pada aksi baca.

---

## 4. Kebutuhan Fungsional (*Functional Requirements*)

### FR-01 — Autentikasi & Otorisasi

* Pengguna login dengan `username` dan kata sandi; sistem menerbitkan *Access Token* JWT berumur **15 menit** dan *Refresh Token* berumur **7 hari**.
* *Access Token* memuat minimal `sub` (id pengguna), `jti`, `iat`, dan `exp`. Peran dan status aktif pengguna **diverifikasi dari database pada setiap request**, sehingga perubahan peran atau penonaktifan langsung berlaku tanpa menunggu token kedaluwarsa.
* *Refresh Token* berupa string acak opak, hanya disimpan dalam bentuk *hash*, dan dirotasi pada setiap penggunaan (token lama otomatis berstatus *revoked*). Penggunaan ulang token yang sudah *revoked* dianggap indikasi pencurian: seluruh *Refresh Token* aktif milik pengguna tersebut dicabut dan kejadian dicatat pada *Audit Log*.
* *Logout* mencabut *Refresh Token* yang dipakai. Penonaktifan pengguna dan penggantian kata sandi mencabut seluruh *Refresh Token* milik pengguna.
* Lima kali kegagalan login berturut-turut mengunci akun selama 15 menit. Setiap kegagalan login tercatat pada *Audit Log*.
* Seluruh endpoint selain `login`, `refresh`, dan `health` mewajibkan *Bearer Token*. Endpoint operasional/admin juga memeriksa permission sesuai Matriks 3.1; endpoint profil sendiri dan menu milik pengguna hanya memerlukan autentikasi.
* Struktur menu navigasi disimpan di tabel `menus` (hierarki `parent_id`, `sort_order`, `path`, `icon`, dan `permission_id` opsional ke `permissions`). Klien *frontend* mengambil pohon menu aktif yang diizinkan untuk pengguna melalui `GET /api/v1/menus/my-menu`. Menu dengan `permission_id` hanya ditampilkan bila pengguna memiliki permission tersebut. Menu induk tanpa permission ditampilkan bila memiliki anak yang terlihat; menu mandiri tanpa permission ditampilkan bagi setiap pengguna terautentikasi. Menu tidak aktif dan anak yang tidak diizinkan tidak dikembalikan.
* Pengguna dengan `user:manage` dapat melihat daftar/detail menu, membuat menu, dan memperbarui atau menonaktifkan menu. Penghapusan permanen tidak tersedia. Perubahan menu dicatat pada *Audit Log*.

### FR-02 — Master Data

* Operasi *Create*, *Read*, *Update*, dan penonaktifan (*soft deactivate* melalui atribut `is_active`) untuk Kategori, Satuan (UoM), Barang (SKU unik), Pemasok, Gudang, dan Lokasi Penyimpanan. **Tidak ada penghapusan permanen (*hard delete*)** pada master data maupun dokumen transaksi.
* Setiap Barang memiliki tepat satu UoM dasar. UoM memiliki atribut `allow_decimal`; bila `FALSE`, seluruh kuantitas barang ber-UoM tersebut harus bilangan bulat.
* SKU tidak dapat diubah setelah barang dipakai pada transaksi apa pun.
* Gudang memiliki atribut `allow_negative_stock` (bawaan `FALSE`) yang hanya dapat diubah oleh Super Admin dan tercatat pada *Audit Log*.
* Kode lokasi bersifat unik di dalam satu gudang.
* Aturan penonaktifan dijelaskan pada bagian 6.8.

### FR-03 — Multi-Gudang & Stok

* Saldo stok disimpan per kombinasi `(warehouse_id, location_id, item_id)` pada `inventory_balances`; baris saldo dibuat otomatis saat pergerakan pertama (nilai awal 0).
* Sistem menyediakan tampilan stok per lokasi, per gudang, dan agregat lintas gudang, dengan filter barang, kategori, dan gudang.
* Tampilan stok memuat kolom **stok dalam perjalanan** (*in-transit*) yang dihitung dari baris Transfer berstatus `SHIPPED` yang belum `RECEIVED`.
* Saldo awal stok dimasukkan melalui Stock Opname (selisih positif terhadap `qty_system = 0`).

### FR-04 — Purchase Order (PO)

* PO memiliki *header* (pemasok, **gudang tujuan**, tanggal pesan, catatan) dan satu atau lebih baris (*PO Lines*) yang masing-masing mereferensikan barang dengan `qty_ordered > 0`. Satu barang hanya boleh muncul satu kali per PO.
* Setiap baris PO melacak `qty_ordered` dan akumulasi `qty_received`, dengan batas `0 ≤ qty_received ≤ qty_ordered`.
* Header dan baris PO hanya dapat diubah saat berstatus `DRAFT`.
* Status PO `PARTIALLY_RECEIVED` dan `RECEIVED` ditentukan otomatis oleh sistem (lihat 5.1).

### FR-05 — Penerimaan Barang (*Goods Receipt*)

* Sistem mengizinkan beberapa dokumen GR untuk satu PO selama status PO adalah `ISSUED` atau `PARTIALLY_RECEIVED`.
* GR harus ditujukan ke gudang yang sama dengan gudang tujuan PO; lokasi penyimpanan ditentukan pada **setiap baris GR**.
* Setiap baris GR mereferensikan satu baris PO (`po_line_id`) dengan `qty_received > 0`; barang di luar PO tidak dapat diterima.
* Validasi kuantitas dilakukan saat GR dibuat/diubah (peringatan awal) dan **dihitung ulang saat posting** di bawah penguncian baris (menjadi keputusan yang mengikat).
* GR berstatus `DRAFT` tidak mencadangkan kuantitas PO; hanya GR `POSTED` yang dihitung.
* Saat GR diselesaikan (`POSTED`), dalam satu transaksi atomik: stok gudang tujuan bertambah, `qty_received` pada baris PO diperbarui, status PO dievaluasi ulang, *ledger* dan *audit log* ditulis.

### FR-06 — Transfer Stok

* Transfer memiliki *header* (gudang & lokasi asal, gudang & lokasi tujuan, catatan) dan satu atau lebih baris (barang, `qty > 0`).
* Alur status: `DRAFT` → `APPROVED` (oleh *Warehouse Manager*) → `SHIPPED` (mengurangi stok asal) → `RECEIVED` (menambah stok tujuan).
* Kuantitas yang dikirim sama dengan `qty` rencana. Saat penerimaan, pengguna mengisi `qty_received` per baris dengan `0 ≤ qty_received ≤ qty`. Bila `qty_received < qty`, **alasan selisih (`variance_reason`) wajib diisi**.
* Selisih penerimaan **tidak dikembalikan ke gudang asal**; barang yang hilang/rusak di perjalanan dicatat sebagai selisih pada baris Transfer dan tidak menambah stok mana pun.
* Transfer antar-lokasi dalam gudang yang sama tetap menggunakan dua tahapan yang sama.

### FR-07 — Stock Opname

* Sesi Opname memiliki cakupan satu gudang, dengan opsi dibatasi pada satu lokasi. Pada satu lokasi hanya boleh ada **satu sesi Opname aktif** (`IN_PROGRESS` atau `WAITING_APPROVAL`) pada satu waktu.
* Saat sesi dimulai (`IN_PROGRESS`), sistem mengambil potret saldo (`qty_system`) untuk seluruh saldo pada cakupan sesi dan **membekukan** lokasi-lokasi tersebut (lihat 6.6).
* Petugas mengisi `qty_physical ≥ 0` per baris. Barang yang ditemukan secara fisik tetapi tidak memiliki saldo dapat ditambahkan sebagai baris baru dengan `qty_system = 0`.
* Selisih dihitung sebagai `qty_variance = qty_physical − qty_system`.
* Setelah seluruh baris terisi, petugas mengajukan persetujuan (`WAITING_APPROVAL`). *Warehouse Manager* dapat menyetujui (`COMPLETED`) atau menolak dengan alasan wajib (kembali ke `IN_PROGRESS` untuk dihitung ulang).
* Saat `COMPLETED`, untuk setiap baris dengan `qty_variance ≠ 0`, sistem menyamakan saldo dengan `qty_physical` dan menulis *ledger* `ADJUSTMENT_PLUS`/`ADJUSTMENT_MINUS`. Baris dengan selisih 0 tidak menghasilkan *ledger*.

### FR-08 — Buku Besar Stok (*Ledger*)

* Setiap perubahan kuantitas stok akibat GR, Transfer Stok, atau Stock Opname wajib menghasilkan baris baru pada `stock_movements`, minimal memuat: tipe pergerakan, gudang, lokasi, barang, `qty_before`, `qty_change` (bertanda: positif untuk penambahan, negatif untuk pengurangan), `qty_after`, referensi dokumen (`reference_type`, `reference_id`), pengguna pelaksana, dan waktu.
* Invarian: `qty_after = qty_before + qty_change`, dan `qty_after` baris terakhir untuk sebuah `(warehouse_id, location_id, item_id)` sama dengan `inventory_balances.qty_on_hand`.
* Tipe pergerakan didefinisikan pada 5.3.

### FR-09 — Audit Log

* Setiap aksi perubahan data master, perubahan status transaksi, perubahan hak akses/penugasan gudang, dan aktivitas autentikasi penting (login berhasil/gagal, logout, penggunaan ulang *Refresh Token* yang sudah dicabut) wajib tercatat otomatis.
* Setiap entri memuat: `user_id` (kosong untuk login gagal yang tidak dikenali), `action`, `entity_type`, `entity_id`, `old_values` dan `new_values` (JSONB), alamat IP, dan waktu.
* Data sensitif (kata sandi, *hash* kata sandi, token) **tidak boleh** muncul pada `old_values`/`new_values`.

### FR-10 — Penomoran Dokumen

* Setiap PO, GR, Transfer, dan Opname memiliki nomor dokumen unik yang dibuat server saat dokumen dibuat, berformat `{PREFIX}-{YYYYMM}-{NNNN}` dengan prefix `PO`, `GR`, `TRF`, dan `OPN` (contoh: `PO-202610-0001`). Urutan di-*reset* tiap bulan dan dibuat aman terhadap akses bersamaan.
* Nomor dokumen yang dibatalkan tidak dipakai ulang (celah urutan diperbolehkan).

### FR-11 — Pencarian & Pagination

* Seluruh endpoint daftar mendukung pagination (`limit` bawaan 50, maksimum 200; `offset`), pengurutan, dan filter yang relevan (status, gudang, barang, rentang tanggal, pencarian teks untuk master data).
* Pembacaan *ledger* wajib dibatasi pagination dan mendukung filter rentang tanggal.

---

## 5. Alur Bisnis & Siklus Status Transaksi

### 5.1. Siklus Status Transaksi (*State Machines*)

Perubahan status hanya dapat dilakukan melalui endpoint aksi khusus (misalnya `POST /purchase-orders/{id}/issue`), bukan dengan mengubah kolom status secara bebas. Setiap transisi di luar tabel di bawah ditolak dengan HTTP 409 (`INVALID_STATE_TRANSITION`).

**Purchase Order (PO)**

| Transisi | Pemicu | Syarat | Efek |
| --- | --- | --- | --- |
| *(baru)* → `DRAFT` | `po:create` | Pemasok dan gudang tujuan aktif | PO dapat diubah; belum dapat dipakai untuk penerimaan. |
| `DRAFT` → `ISSUED` | `po:issue` | Minimal 1 baris; seluruh `qty_ordered > 0`; barang aktif | PO resmi dikirim ke pemasok; baris dikunci dari perubahan; siap menerima GR. |
| `DRAFT` → `CANCELLED` | `po:create` | – | PO dibatalkan. |
| `ISSUED` → `CANCELLED` | `po:cancel` | Belum ada GR `POSTED` dan tidak ada GR `DRAFT` pada PO | PO dibatalkan. |
| `ISSUED` → `PARTIALLY_RECEIVED` | Sistem (saat GR `POSTED`) | Total `qty_received` > 0 dan masih ada baris yang belum penuh | – |
| `ISSUED` / `PARTIALLY_RECEIVED` → `RECEIVED` | Sistem (saat GR `POSTED`) | **Seluruh** baris memiliki `qty_received = qty_ordered` | Status final. |
| `ISSUED` / `PARTIALLY_RECEIVED` → `CLOSED` | `po:close` | Tidak ada GR `DRAFT` pada PO; alasan penutupan wajib | Sisa pesanan yang belum dikirim disepakati tidak dilanjutkan. Status final. |

Catatan: GR berikutnya pada PO berstatus `PARTIALLY_RECEIVED` yang masih menyisakan kuantitas tidak mengubah status.

**Goods Receipt (GR)**

| Transisi | Pemicu | Syarat | Efek |
| --- | --- | --- | --- |
| *(baru)* → `DRAFT` | `gr:manage` | PO berstatus `ISSUED`/`PARTIALLY_RECEIVED`; pengguna ditugaskan pada gudang tujuan | Dokumen disiapkan; belum mengubah stok. |
| `DRAFT` → `POSTED` | `gr:manage` | Status PO dicek ulang; validasi *over-receipt* (6.2); lokasi valid, aktif, dan tidak dibekukan | Menambah saldo stok, menulis *ledger* `IN_PURCHASE`, memperbarui `qty_received` baris PO dan status PO. Status final. |
| `DRAFT` → `CANCELLED` | `gr:manage` | – | Dokumen dibatalkan. |

Koreksi atas GR `POSTED` tidak dilakukan lewat pembalikan dokumen, melainkan melalui Stock Opname.

**Stock Transfer**

| Transisi | Pemicu | Syarat | Efek |
| --- | --- | --- | --- |
| *(baru)* → `DRAFT` | `transfer:create` | Asal ≠ tujuan (6.3); lokasi valid dan aktif | Rencana transfer dibuat; belum memengaruhi stok. |
| `DRAFT` → `APPROVED` | `transfer:approve` | Minimal 1 baris; `qty > 0` | Transfer disetujui; belum memengaruhi stok. |
| `DRAFT` / `APPROVED` → `CANCELLED` | `transfer:create` (untuk `DRAFT`), `transfer:approve` (untuk `APPROVED`) | – | Transfer dibatalkan. |
| `APPROVED` → `SHIPPED` | `transfer:ship` | Stok asal mencukupi (6.1); lokasi asal tidak dibekukan | Mengurangi stok asal, menulis *ledger* `OUT_TRANSFER`. Barang berstatus *in-transit*. |
| `SHIPPED` → `RECEIVED` | `transfer:receive` | `0 ≤ qty_received ≤ qty` per baris; alasan wajib bila kurang; lokasi tujuan aktif dan tidak dibekukan | Menambah stok tujuan sebesar `qty_received`, menulis *ledger* `IN_TRANSFER` (hanya untuk baris dengan `qty_received > 0`). Status final. |

**Stock Opname**

| Transisi | Pemicu | Syarat | Efek |
| --- | --- | --- | --- |
| *(baru)* → `DRAFT` | `opname:manage` | Gudang/lokasi aktif | Penjadwalan opname pada gudang/lokasi tertentu. |
| `DRAFT` → `IN_PROGRESS` | `opname:manage` | Tidak ada opname aktif lain pada lokasi dalam cakupan | Mengambil *snapshot* `qty_system` dan membekukan lokasi dalam cakupan. |
| `DRAFT` → `CANCELLED` | `opname:manage` | – | Opname dibatalkan. |
| `IN_PROGRESS` → `WAITING_APPROVAL` | `opname:count` | Seluruh baris memiliki `qty_physical ≥ 0` | Menunggu tinjauan *Warehouse Manager* atas selisih. Pembekuan tetap berlaku. |
| `IN_PROGRESS` → `CANCELLED` | `opname:manage` | – | Pembekuan dilepas; stok tidak berubah. |
| `WAITING_APPROVAL` → `COMPLETED` | `opname:approve` | – | Menyamakan saldo dengan `qty_physical` dan menulis *ledger* `ADJUSTMENT_PLUS`/`ADJUSTMENT_MINUS` untuk baris yang berselisih; pembekuan dilepas. Status final. |
| `WAITING_APPROVAL` → `IN_PROGRESS` | `opname:approve` | Alasan penolakan wajib | Dihitung ulang oleh petugas. |

### 5.2. Rincian Alur Bisnis Utama

1. **Alur Penerimaan Barang Parsial (PO ke GR):**
   * *Purchasing Staff* menerbitkan PO untuk Barang A sebanyak 100 unit ke Gudang A (`ISSUED`).
   * Pemasok mengirim pengiriman pertama sebanyak 40 unit. *Warehouse Staff* Gudang A membuat GR #1 sebesar 40 unit dan memposting-nya (`POSTED`).
   * Sistem memvalidasi bahwa 40 tidak melebihi sisa pesanan (100), menambah stok sebesar 40, mengubah `qty_received` baris PO menjadi 40, dan memperbarui status PO menjadi `PARTIALLY_RECEIVED`.
   * Pemasok mengirim pengiriman kedua sebanyak 60 unit. *Warehouse Staff* membuat GR #2 sebesar 60 unit (`POSTED`).
   * Sistem menambah stok sebesar 60, mengubah `qty_received` baris PO menjadi 100, dan otomatis mengubah status PO menjadi `RECEIVED`.

2. **Alur Transfer Stok Antar-Gudang:**
   * *Warehouse Staff* Gudang A membuat dokumen Transfer dari Gudang A (Lokasi A1) ke Gudang B (Lokasi B1) sebanyak 25 unit (`DRAFT`).
   * *Warehouse Manager* Gudang A menyetujui Transfer (`APPROVED`).
   * Saat barang dikirim (`SHIPPED`), sistem mengunci baris saldo Gudang A (Lokasi A1), memvalidasi ketersediaan stok minimal 25 unit, lalu memotong stok sebesar 25 unit. Barang berstatus *in-transit*.
   * Saat barang tiba di Gudang B, *Warehouse Staff* Gudang B mengonfirmasi penerimaan (`RECEIVED`) dengan mengisi `qty_received`. Stok Gudang B (Lokasi B1) bertambah sebesar `qty_received`. Bila diterima 23 dari 25, sistem mewajibkan alasan selisih (misalnya barang rusak di jalan) dan mencatat selisih 2 pada baris Transfer.

3. **Alur Stock Opname:**
   * *Warehouse Manager* membuat sesi Opname untuk Gudang A dan memulainya (`IN_PROGRESS`). Sistem mengambil *snapshot* `qty_system` dan membekukan lokasi pada cakupan; GR dan Transfer yang menyentuh lokasi tersebut ditolak selama pembekuan.
   * *Warehouse Staff* menghitung fisik dan mengisi `qty_physical` per baris, lalu mengajukan persetujuan (`WAITING_APPROVAL`).
   * *Warehouse Manager* meninjau selisih. Bila disetujui (`COMPLETED`), saldo disamakan dengan hasil hitung fisik dan *ledger* penyesuaian dicatat. Bila ditolak, sesi kembali ke `IN_PROGRESS` dengan alasan penolakan.

4. **Alur Saldo Awal Stok:** Untuk mengisi stok awal gudang yang baru, *Warehouse Manager* membuat sesi Opname pada gudang tersebut, petugas menambahkan baris barang dengan `qty_system = 0` dan mengisi `qty_physical`, lalu disetujui sehingga tercatat sebagai `ADJUSTMENT_PLUS`.

### 5.3. Jenis Pergerakan Stok (*Movement Types*)

| Tipe | Pemicu | Arah (`qty_change`) | `reference_type` |
| --- | --- | --- | --- |
| `IN_PURCHASE` | GR → `POSTED` | Positif | `GOODS_RECEIPT` |
| `OUT_TRANSFER` | Transfer → `SHIPPED` | Negatif | `STOCK_TRANSFER` |
| `IN_TRANSFER` | Transfer → `RECEIVED` | Positif | `STOCK_TRANSFER` |
| `ADJUSTMENT_PLUS` | Opname → `COMPLETED` (selisih positif) | Positif | `STOCK_OPNAME` |
| `ADJUSTMENT_MINUS` | Opname → `COMPLETED` (selisih negatif) | Negatif | `STOCK_OPNAME` |

---

## 6. Aturan Validasi & Ketentuan Bisnis

### 6.1. Pencegahan Stok Negatif (*Negative Stock Prevention*)

* Secara bawaan, setiap gudang memiliki `allow_negative_stock = FALSE`.
* Transaksi yang mengurangi stok melalui pengiriman Transfer Stok harus memvalidasi bahwa `qty_on_hand − qty_deducted ≥ 0`. Validasi dilakukan **di lapisan aplikasi, di dalam transaksi, setelah baris saldo dikunci**.
* Jika hasil pengurangan kurang dari 0 dan `allow_negative_stock = FALSE`, transaksi ditolak seluruhnya (*atomic rollback*) dengan HTTP 409, kode `INSUFFICIENT_STOCK`, dan rincian (barang, stok tersedia, kuantitas diminta).
* Karena aturan ini berlaku **per gudang**, tidak dipasang `CHECK (qty_on_hand >= 0)` pada level tabel; penegakannya ada pada lapisan aplikasi di bawah penguncian.
* Stock Opname tidak terdampak aturan ini karena `qty_physical` wajib `≥ 0`, sehingga saldo hasil penyesuaian tidak pernah negatif.
* Bila `allow_negative_stock = TRUE`, pengiriman Transfer boleh membuat saldo negatif dan `qty_after` pada *ledger* mencatat nilai negatif tersebut.

### 6.2. Validasi Kuantitas Penerimaan PO (*Over-Receipt Prevention*)

* Kuantitas yang diterima pada baris GR harus bernilai lebih dari 0.
* Berlaku aturan tegas: `qty_received_current_gr + po_line.qty_received ≤ po_line.qty_ordered`, dengan `po_line.qty_received` hanya menghitung GR berstatus `POSTED`. Sistem menolak (HTTP 409, `OVER_RECEIPT`) penerimaan yang melebihi jumlah pesanan.
* Pemeriksaan pada saat posting dilakukan setelah baris PO terkait dikunci (`SELECT ... FOR UPDATE`), sehingga dua GR yang diposting bersamaan tidak dapat sama-sama lolos.

### 6.3. Validasi Lokasi dan Gudang

* Lokasi penyimpanan yang dipilih pada transaksi harus berstatus aktif dan benar-benar dimiliki oleh gudang yang bersangkutan (kode `INVALID_LOCATION`). Gudang, barang, dan pemasok yang dipakai pada dokumen baru juga harus aktif (kode `INACTIVE_REFERENCE`).
* Pada Transfer Stok, kombinasi `(source_warehouse_id, source_location_id)` tidak boleh sama dengan `(destination_warehouse_id, destination_location_id)`.
* Pada PO, satu barang hanya boleh muncul satu kali per PO.

### 6.4. Imutabilitas Buku Besar & Audit Log

* Data pada tabel `stock_movements` dan `audit_logs` bersifat *append-only*. Tidak ada peran pengguna (termasuk *Super Admin*) yang diizinkan melakukan `UPDATE` atau `DELETE` pada kedua tabel tersebut dari aplikasi.
* Aturan ini **ditegakkan juga di level database**: *trigger* yang menolak `UPDATE`/`DELETE`, serta role database aplikasi yang tidak diberi hak `UPDATE`, `DELETE`, dan `TRUNCATE` pada kedua tabel.
* Koreksi dilakukan dengan menambah baris baru (misalnya penyesuaian Opname), tidak pernah dengan mengubah baris lama.

### 6.5. Pengendalian Konkurensi (*Concurrency Control*)

* Saat memproses perubahan stok (GR `POSTED`, Transfer `SHIPPED`/`RECEIVED`, Opname `COMPLETED`), sistem wajib menggunakan *row-level locking* (`SELECT ... FOR UPDATE`) pada baris dokumen, baris PO terkait, dan baris saldo stok.
* **Urutan penguncian seragam** untuk mencegah *deadlock*: (1) baris *header* dokumen, (2) baris PO terkait bila ada, (3) baris lokasi penyimpanan (`FOR SHARE` untuk pemeriksaan pembekuan pada 6.6, `FOR UPDATE` saat Opname dimulai) diurutkan berdasarkan `id`, (4) baris saldo stok diurutkan berdasarkan `(warehouse_id, location_id, item_id)`.
* Baris saldo yang belum ada dibuat melalui *upsert* (`INSERT ... ON CONFLICT DO NOTHING`) sebelum dikunci, mengandalkan *unique constraint* `(warehouse_id, location_id, item_id)`.
* Setiap transisi status dijaga terhadap status yang diharapkan di dalam transaksi; bila dua permintaan memproses dokumen yang sama bersamaan, hanya satu yang berhasil dan yang lain ditolak dengan HTTP 409 (`INVALID_STATE_TRANSITION`), sehingga stok tidak pernah terposting ganda.

### 6.6. Pembekuan Lokasi Selama Stock Opname

* Selama sesi Opname berstatus `IN_PROGRESS` atau `WAITING_APPROVAL`, lokasi dalam cakupan sesi dianggap **dibekukan**: posting GR, pengiriman Transfer dari lokasi tersebut, dan penerimaan Transfer ke lokasi tersebut ditolak dengan HTTP 409 (`LOCATION_FROZEN`).
* Pembekuan dilepas saat sesi `COMPLETED` atau `CANCELLED`. Transfer yang sudah `SHIPPED` tetap menunggu di status *in-transit* hingga lokasi tujuan tidak lagi dibekukan.

### 6.7. Aturan Selisih Penerimaan Transfer

* `qty_received` tidak boleh melebihi `qty` yang dikirim (HTTP 409, `TRANSFER_QTY_EXCEEDS_SHIPPED`).
* `qty_received < qty` mewajibkan `variance_reason` (HTTP 422 bila kosong).
* Selisih tidak menghasilkan baris *ledger*; jejaknya tersimpan pada baris Transfer dan terbaca dari pasangan `OUT_TRANSFER` dan `IN_TRANSFER`.

### 6.8. Aturan Penonaktifan & Perubahan Master Data

* Gudang, lokasi, dan barang tidak dapat dinonaktifkan jika masih memiliki saldo ≠ 0 atau masih dipakai pada dokumen yang belum final (PO `DRAFT`/`ISSUED`/`PARTIALLY_RECEIVED`, GR `DRAFT`, Transfer `DRAFT`/`APPROVED`/`SHIPPED`, Opname `DRAFT`/`IN_PROGRESS`/`WAITING_APPROVAL`). Pelanggaran ditolak dengan HTTP 409 (`ENTITY_IN_USE`).
* Pemasok tidak dapat dinonaktifkan jika masih memiliki PO yang belum final.
* SKU barang tidak dapat diubah setelah dipakai pada transaksi.

### 6.9. Aturan Kuantitas & Presisi

* Seluruh kuantitas disimpan sebagai `NUMERIC(18, 4)`; kuantitas pada baris dokumen harus `> 0` (kecuali `qty_physical` pada Opname dan `qty_received` pada penerimaan Transfer yang boleh 0), dengan maksimum 4 angka di belakang koma.
* Kuantitas pada barang ber-UoM `allow_decimal = FALSE` harus bilangan bulat.

---

## 7. Kebutuhan Non-Fungsional (*Non-Functional Requirements*)

### 7.1. Integritas Transaksional (ACID)

* Seluruh pembaruan status dokumen, perubahan saldo stok (`inventory_balances`), pencatatan buku besar (`stock_movements`), dan pencatatan `audit_logs` dalam satu aksi bisnis harus dieksekusi di dalam satu transaksi database (*single database transaction*). Jika salah satu langkah gagal, seluruh perubahan dibatalkan (*rollback*).
* Batas transaksi berada pada satu *use case* di lapisan service, bukan tersebar di beberapa lapisan.

### 7.2. Keamanan (*Security*)

* Kata sandi wajib di-*hash* menggunakan `Argon2id` (pilihan utama) atau `bcrypt`; panjang minimal kata sandi 8 karakter.
* *Access Token* JWT berumur 15 menit, ditandatangani dengan HS256 menggunakan kunci rahasia dari variabel lingkungan (minimal 32 byte); RS256 dapat dipakai bila diperlukan di kemudian hari.
* *Refresh Token* berumur 7 hari, disimpan dalam bentuk *hash*, dirotasi, dan dapat dicabut (lihat FR-01).
* Seluruh query SQL wajib **berparameter**; dilarang menyusun SQL dengan penggabungan string dari input pengguna.
* Rahasia (kunci JWT, kredensial database) hanya dibaca dari variabel lingkungan dan tidak disimpan di repositori. Kata sandi dan token tidak boleh muncul di log aplikasi.
* Pembatasan login dan penguncian akun sesuai FR-01. TLS diterminasi pada *reverse proxy*/lingkungan produksi.

### 7.3. Kinerja (*Performance*)

* Waktu respons pembacaan saldo stok dan pencarian master data harus di bawah **200 ms (persentil ke-95)** untuk beban kerja normal melalui indeks yang tepat pada PostgreSQL.
* Asumsi beban kerja normal (asumsi awal, dapat disesuaikan): hingga 20 pengguna bersamaan, 10.000 barang aktif, dan 1.000.000 baris *ledger*.
* Daftar data wajib dipaginasi (FR-11); *ledger* dibaca dengan filter rentang tanggal.

### 7.4. Presisi Numerik

* Seluruh kuantitas disimpan menggunakan `NUMERIC(18, 4)` (bukan `FLOAT`/`REAL`) dan ditangani sebagai `Decimal` di Python.
* Pada JSON API, kuantitas dikirim sebagai **string desimal** (contoh `"12.5000"`) agar tidak kehilangan presisi pada klien.

### 7.5. Akses Data & Migrasi (PostgreSQL Langsung)

* Aplikasi mengakses PostgreSQL langsung melalui driver (disarankan `psycopg` 3 dengan *connection pool*) tanpa ORM. Seluruh SQL berada pada lapisan *repository*.
* Skema dan perubahannya dikelola sebagai berkas migrasi `.sql` berurutan (`NNN_deskripsi.sql`), dijalankan oleh *runner* sederhana yang mencatat versi terapan pada tabel `schema_migrations`. Migrasi bersifat *forward-only*.
* Konvensi penamaan *constraint* dan indeks eksplisit: `pk_<tabel>`, `fk_<tabel>_<kolom>`, `uq_<tabel>_<kolom>`, `ck_<tabel>_<aturan>`, `ix_<tabel>_<kolom>`.
* Kunci utama memakai `BIGINT GENERATED ALWAYS AS IDENTITY`; seluruh waktu memakai `TIMESTAMPTZ` (UTC).
* Integritas tambahan di level database: *composite foreign key* agar lokasi pasti milik gudang yang dirujuk, `UNIQUE (warehouse_id, location_id, item_id)` pada saldo stok, `CHECK` untuk status valid dan `qty > 0` pada baris dokumen, serta *trigger* imutabilitas (6.4).

### 7.6. Operasional & Kualitas

* Log terstruktur dengan *request id* (`X-Request-ID`) pada setiap permintaan, dan endpoint `GET /health` untuk pemeriksaan kesehatan layanan.
* Setiap kriteria penerimaan pada bagian 8 diverifikasi oleh pengujian otomatis terhadap database PostgreSQL sungguhan (bukan *mock*).
* Dokumentasi API (OpenAPI/Swagger) dihasilkan otomatis oleh FastAPI.

---

## 8. Kriteria Penerimaan (*Acceptance Criteria*)

1. **AC-01 (Penerimaan Parsial & Pemenuhan PO):**
   * *Given* sebuah PO berstatus `ISSUED` dengan pesanan 50 unit Barang X,
   * *When* pengguna mem-posting GR pertama sebesar 20 unit, *Then* status PO berubah menjadi `PARTIALLY_RECEIVED`, `qty_received` pada baris PO menjadi 20, dan saldo stok bertambah 20.
   * *When* pengguna mencoba mem-posting GR kedua sebesar 35 unit, *Then* sistem menolak transaksi (`OVER_RECEIPT`) karena total penerimaan (55) melebihi pesanan (50).
   * *When* pengguna mem-posting GR kedua sebesar 30 unit, *Then* status PO otomatis berubah menjadi `RECEIVED` dan saldo stok bertambah 30.

2. **AC-02 (Pencegahan Stok Negatif):**
   * *Given* saldo Barang Y di Gudang A adalah 10 unit, konfigurasi `allow_negative_stock` pada Gudang A adalah `FALSE`, dan sebuah Transfer 12 unit dari Gudang A berstatus `APPROVED`,
   * *When* pengguna mengubah status Transfer menjadi `SHIPPED`,
   * *Then* sistem membatalkan transaksi, mengembalikan penolakan `INSUFFICIENT_STOCK`, dan memastikan saldo stok tetap 10 unit serta status Transfer tetap `APPROVED`.

3. **AC-03 (Konsistensi Transfer Antar-Gudang):**
   * *Given* Transfer Stok 15 unit dari Gudang A ke Gudang B berstatus `APPROVED`,
   * *When* status diubah menjadi `SHIPPED`, *Then* stok Gudang A berkurang 15 unit, tercatat 1 baris `OUT_TRANSFER` di `stock_movements`, dan stok Gudang B belum bertambah.
   * *When* status diubah menjadi `RECEIVED` dengan `qty_received` 15, *Then* stok Gudang B bertambah 15 unit dan tercatat 1 baris `IN_TRANSFER` di `stock_movements`.

4. **AC-04 (Rekonsiliasi Stock Opname):**
   * *Given* sebuah sesi *Stock Opname* di mana `qty_system` tercatat 100 unit dan petugas memasukkan `qty_physical` 97 unit,
   * *When* *Warehouse Manager* menyetujui opname menjadi `COMPLETED`,
   * *Then* sistem mencatat `qty_variance` sebesar `-3`, memperbarui saldo stok menjadi 97 unit, dan membuat baris `stock_movements` bertipe `ADJUSTMENT_MINUS` dengan `qty_change` `-3`, `qty_before` 100, dan `qty_after` 97.

5. **AC-05 (Kepatuhan RBAC & Audit Log):**
   * *Given* pengguna dengan peran *Warehouse Staff*,
   * *When* pengguna tersebut mencoba menerbitkan PO atau menyetujui akhir *Stock Opname*, *Then* sistem menolak akses (HTTP 403 Forbidden).
   * *When* perubahan data yang sah berhasil dilakukan oleh pengguna mana pun, *Then* satu baris baru otomatis tercatat di tabel `audit_logs` dengan informasi pengguna, waktu, identitas entitas, serta data sebelum dan sesudah perubahan.

6. **AC-06 (Konkurensi Pengiriman):**
   * *Given* saldo Barang Y di Lokasi A1 adalah 10 unit dengan `allow_negative_stock = FALSE`, dan dua Transfer berbeda masing-masing 8 unit dari Lokasi A1 berstatus `APPROVED`,
   * *When* kedua Transfer diubah menjadi `SHIPPED` secara bersamaan,
   * *Then* tepat satu berhasil dan satu ditolak dengan `INSUFFICIENT_STOCK`, saldo akhir 2 unit, dan hanya ada 1 baris `OUT_TRANSFER`.

7. **AC-07 (Atomisitas Transaksi):**
   * *Given* sebuah GR berstatus `DRAFT`,
   * *When* posting gagal pada langkah mana pun (misalnya penulisan *ledger* atau *audit log* gagal),
   * *Then* status GR tetap `DRAFT`, saldo stok dan `qty_received` pada baris PO tidak berubah, dan tidak ada baris *ledger* maupun *audit log* yang tersisa.

8. **AC-08 (Imutabilitas):**
   * *Given* baris pada `stock_movements` dan `audit_logs`,
   * *When* `UPDATE` atau `DELETE` dicoba terhadap kedua tabel tersebut, termasuk lewat koneksi SQL langsung memakai role database aplikasi,
   * *Then* operasi ditolak oleh database dan data tidak berubah.

9. **AC-09 (Selisih Penerimaan Transfer):**
   * *Given* Transfer 25 unit berstatus `SHIPPED`,
   * *When* penerimaan diisi `qty_received` 23 tanpa alasan selisih, *Then* sistem menolak (HTTP 422).
   * *When* diisi 23 dengan alasan selisih, *Then* stok tujuan bertambah 23, tercatat 1 baris `IN_TRANSFER` sebesar 23, dan selisih 2 tersimpan pada baris Transfer.
   * *When* diisi 26, *Then* sistem menolak (`TRANSFER_QTY_EXCEEDS_SHIPPED`).

10. **AC-10 (Pembekuan Lokasi Opname):**
    * *Given* sesi Opname berstatus `IN_PROGRESS` pada Lokasi X,
    * *When* pengguna mencoba memposting GR ke Lokasi X atau mengirim Transfer dari Lokasi X, *Then* sistem menolak dengan `LOCATION_FROZEN`.
    * *When* sesi Opname menjadi `COMPLETED` atau `CANCELLED`, *Then* transaksi pada Lokasi X dapat dilakukan kembali.

11. **AC-11 (Siklus *Refresh Token*):**
    * *Given* pengguna memiliki *Refresh Token* R1 yang valid,
    * *When* R1 dipakai untuk memperbarui sesi, *Then* sistem menerbitkan token baru R2 dan R1 berstatus *revoked*.
    * *When* R1 dipakai lagi, *Then* sistem menolak (HTTP 401), mencabut seluruh *Refresh Token* aktif pengguna tersebut, dan mencatat kejadian pada *Audit Log*.
    * *When* pengguna melakukan *logout*, *Then* *Refresh Token* yang dipakai tidak dapat dipakai lagi.

12. **AC-12 (Warehouse Scoping):**
    * *Given* *Warehouse Staff* yang hanya ditugaskan pada Gudang A,
    * *When* pengguna tersebut mencoba memposting GR untuk PO yang gudang tujuannya Gudang B, *Then* sistem menolak (HTTP 403, `WAREHOUSE_NOT_ASSIGNED`).

13. **AC-13 (Pencegahan Posting Ganda):**
    * *Given* sebuah GR berstatus `DRAFT` sebesar 10 unit,
    * *When* dua permintaan posting untuk GR yang sama dikirim bersamaan, *Then* tepat satu berhasil, saldo stok bertambah hanya 10 unit, `qty_received` PO bertambah hanya 10, dan permintaan lainnya ditolak dengan `INVALID_STATE_TRANSITION`.

14. **AC-14 (Menu Dinamis Berbasis Permission):**
    * *Given* menu aktif tersusun sebagai hierarki dan sebagian menu memiliki `permission_id`, *When* pengguna terautentikasi meminta `GET /api/v1/menus/my-menu`, *Then* API mengembalikan pohon berurutan `sort_order` lalu `id`, hanya berisi menu aktif yang permission-nya dimiliki pengguna; menu induk tanpa permission hanya muncul jika memiliki anak yang terlihat, sedangkan menu mandiri tanpa permission terlihat bagi pengguna terautentikasi.
    * *Given* pengguna tidak memiliki `user:manage`, *When* ia meminta operasi administrasi menu, *Then* permintaan ditolak dengan HTTP 403 dan `PERMISSION_DENIED`.
    * *Given* pengguna memiliki `user:manage`, *When* ia membuat atau memperbarui menu yang valid, *Then* perubahan tersimpan dan tercatat pada *Audit Log*; kode menu duplikat ditolak dengan `DUPLICATE`, referensi permission/parent yang tidak ada ditolak, siklus hierarki ditolak dengan `VALIDATION_ERROR`, dan menu induk dengan submenu aktif tidak dapat dinonaktifkan (`ENTITY_IN_USE`).

---

## Lampiran A — Entitas Data Utama

Daftar ini menjadi acuan penyusunan berkas migrasi. Kolom audit umum (`created_at`, `updated_at`, `created_by`) berlaku pada seluruh tabel kecuali tabel *append-only* (yang hanya memiliki `created_at`).

| Tabel | Kolom kunci & catatan |
| --- | --- |
| `roles` | `name` (unik); diisi awal 5 peran. |
| `permissions` | `code` (unik, mis. `po:issue`); diisi awal sesuai Matriks 3.1. |
| `role_permissions` | `(role_id, permission_id)`; pemetaan peran ke permission. |
| `users` | `username` (unik), `email`, `password_hash`, `full_name`, `role_id`, `is_active`, `failed_login_count`, `locked_until`. |
| `user_warehouses` | `(user_id, warehouse_id)` sebagai kunci utama; penugasan gudang. |
| `refresh_tokens` | `user_id`, `token_hash` (unik), `expires_at`, `revoked_at`, `replaced_by_id`. |
| `menus` | `code` (unik), `name`, `path`, `icon`, `parent_id` (self-FK), `sort_order`, `permission_id` (FK opsional ke `permissions`), `is_active`. |
| `categories` | `name` (unik), `is_active`. |
| `uoms` | `code` (unik), `name`, `allow_decimal`, `is_active`. |
| `items` | `sku` (unik), `name`, `category_id`, `uom_id`, `is_active`. |
| `suppliers` | `code` (unik), `name`, kontak, `is_active`. |
| `warehouses` | `code` (unik), `name`, `allow_negative_stock`, `is_active`. |
| `storage_locations` | `warehouse_id`, `code` (unik per gudang), `is_active`; `UNIQUE (id, warehouse_id)` untuk *composite FK*. |
| `inventory_balances` | `warehouse_id`, `location_id`, `item_id`, `qty_on_hand NUMERIC(18,4)`; `UNIQUE (warehouse_id, location_id, item_id)`; indeks komposit untuk pencarian stok. |
| `stock_movements` | *Append-only*. `movement_type`, `warehouse_id`, `location_id`, `item_id`, `qty_before`, `qty_change`, `qty_after`, `reference_type`, `reference_id`, `created_by`, `created_at`. |
| `purchase_orders` | `po_number` (unik), `supplier_id`, `warehouse_id` (tujuan), `status`, `order_date`, `notes`, `issued_at`, `closed_reason`. |
| `po_lines` | `po_id`, `item_id`, `qty_ordered`, `qty_received`; `UNIQUE (po_id, item_id)`; `CHECK (0 <= qty_received AND qty_received <= qty_ordered)`. |
| `goods_receipts` | `gr_number` (unik), `po_id`, `warehouse_id`, `status`, `received_date`, `posted_at`, `posted_by`. |
| `gr_lines` | `gr_id`, `po_line_id`, `location_id`, `qty_received` (`> 0`). |
| `stock_transfers` | `transfer_number` (unik), `source_warehouse_id`, `source_location_id`, `destination_warehouse_id`, `destination_location_id`, `status`, `approved_by/at`, `shipped_at`, `received_at`. |
| `stock_transfer_lines` | `transfer_id`, `item_id`, `qty` (`> 0`), `qty_received`, `variance_reason`. |
| `stock_opnames` | `opname_number` (unik), `warehouse_id`, `location_id` (opsional; kosong = seluruh gudang), `status`, `started_at`, `approved_by/at`, `rejection_reason`. |
| `stock_opname_lines` | `opname_id`, `location_id`, `item_id`, `qty_system`, `qty_physical`, `qty_variance`. |
| `audit_logs` | *Append-only*. `user_id`, `action`, `entity_type`, `entity_id`, `old_values JSONB`, `new_values JSONB`, `ip_address`, `created_at`. |
| `document_sequences` | `doc_type`, `period` (YYYYMM), `last_value`; dasar penomoran dokumen (FR-10). |
| `schema_migrations` | `version`, `applied_at`; dikelola oleh *runner* migrasi. |

---

## Lampiran B — Konvensi API

* **Base path:** `/api/v1`. Autentikasi dengan header `Authorization: Bearer <access_token>`.
* **Endpoint aksi transisi:** `POST /purchase-orders/{id}/issue|cancel|close`, `POST /goods-receipts/{id}/post|cancel`, `POST /stock-transfers/{id}/approve|ship|receive|cancel`, `POST /stock-opnames/{id}/start|submit|approve|reject|cancel`.
* **Menu navigasi:** `GET /menus/my-menu` mengembalikan pohon menu aktif terfilter untuk pengguna terautentikasi; `GET /menus` dan `GET /menus/{id}` membaca katalog menu untuk `user:manage`; `POST /menus` membuat menu; `PATCH /menus/{id}` memperbarui atau menonaktifkan menu. Body pembuatan menerima `code`, `name`, `path`, `icon`, `parent_id`, `sort_order`, `permission_id`, dan `is_active`; `PATCH` menerima subset field tersebut serta `clear_parent`/`clear_permission` untuk menghapus relasi opsional. Operasi administrasi menu memerlukan `user:manage`; tidak ada endpoint hard delete. Pembuatan mengembalikan HTTP 201.
* **Format waktu:** ISO 8601 UTC. **Format kuantitas:** string desimal.
* **Pagination:** `limit` (bawaan 50, maks 200) dan `offset`; respons berbentuk `{ "items": [...], "total": n, "limit": n, "offset": n }`.
* **Format error:** `{ "error": { "code": "INSUFFICIENT_STOCK", "message": "...", "details": { ... } } }`.

**Katalog kode error**

| Kode | HTTP | Kondisi |
| --- | --- | --- |
| `AUTH_INVALID_CREDENTIALS` | 401 | Username/kata sandi salah. |
| `AUTH_TOKEN_INVALID` | 401 | Token tidak valid, kedaluwarsa, atau sudah dicabut. |
| `AUTH_TOO_MANY_ATTEMPTS` | 429 | Akun terkunci sementara akibat login gagal berulang. |
| `PERMISSION_DENIED` | 403 | Pengguna tidak memiliki permission yang dibutuhkan. |
| `WAREHOUSE_NOT_ASSIGNED` | 403 | Pengguna tidak ditugaskan pada gudang terkait. |
| `NOT_FOUND` | 404 | Data tidak ditemukan. |
| `VALIDATION_ERROR` | 422 | Payload tidak valid (termasuk alasan selisih yang kosong). |
| `INVALID_LOCATION` | 422 | Lokasi tidak aktif atau bukan milik gudang yang dipilih. |
| `INACTIVE_REFERENCE` | 422 | Gudang/barang/pemasok yang dirujuk tidak aktif. |
| `DUPLICATE` | 409 | Pelanggaran keunikan (SKU, kode, nomor dokumen). |
| `INVALID_STATE_TRANSITION` | 409 | Transisi status tidak diizinkan atau dokumen sudah diproses. |
| `INSUFFICIENT_STOCK` | 409 | Stok tidak mencukupi. |
| `OVER_RECEIPT` | 409 | Penerimaan melebihi kuantitas pesanan PO. |
| `TRANSFER_QTY_EXCEEDS_SHIPPED` | 409 | `qty_received` melebihi kuantitas yang dikirim. |
| `LOCATION_FROZEN` | 409 | Lokasi sedang dibekukan oleh Stock Opname. |
| `ENTITY_IN_USE` | 409 | Penonaktifan ditolak karena masih dipakai/bersaldo. |

---

## Lampiran C — Catatan Revisi dari v1

| # | Perubahan | Alasan |
| --- | --- | --- |
| 1 | Teknologi diperjelas: PostgreSQL langsung (tanpa ORM); NFR "Kesiapan ORM & Migrasi" (SQLAlchemy/Alembic) diganti 7.5. | Selaras keputusan pemakaian SQL langsung. |
| 2 | Ditambahkan Matriks Permission (3.1) dan aturan *warehouse scoping* (3.2). | v1 menyebut *scoping* tetapi tidak mendefinisikannya; peran vs aksi belum terukur. |
| 3 | Transfer Stok mendapat status `APPROVED`. | v1 menyatakan *Warehouse Manager* menyetujui Transfer, tetapi state machine langsung `DRAFT` → `SHIPPED`. |
| 4 | PO: "persetujuan" diubah menjadi "penerbitan"; pemicu `CLOSED` diperjelas; PO diberi gudang tujuan. | v1 tidak memiliki status persetujuan PO; peran penutup PO tidak konsisten dengan tabel peran; GR membutuhkan gudang tujuan yang pasti. |
| 5 | Ditambahkan pembekuan lokasi selama Opname (6.6) dan penambahan baris barang tak bersaldo. | Tanpa pembekuan, mutasi yang terjadi setelah *snapshot* akan tertimpa saat saldo disamakan dengan hitung fisik. |
| 6 | Aturan selisih penerimaan Transfer (6.7) dan `qty_received ≤ qty`. | v1 mewajibkan alasan selisih tetapi tidak menjelaskan nasib kuantitas selisih. |
| 7 | Pencegahan stok negatif: validasi di aplikasi di bawah *lock*; tidak memakai `CHECK` tabel; Opname tidak terdampak. | Aturan bersifat per gudang (`allow_negative_stock`); contoh Opname pada v1 tidak mungkin menghasilkan saldo negatif. |
| 8 | Konkurensi: urutan penguncian seragam, *upsert* saldo, penjagaan status, pencegahan posting ganda. | Mencegah *deadlock* dan posting ganda. |
| 9 | Imutabilitas ditegakkan juga di level database. | v1 hanya menyatakan "dari aplikasi". |
| 10 | Detail autentikasi: umur token, rotasi dan deteksi penggunaan ulang *Refresh Token*, pembatasan login, verifikasi peran per request. | v1 hanya menyebut JWT dan *revocation* tanpa rincian. |
| 11 | Ditambahkan FR-10 (penomoran dokumen), FR-11 (pagination), jenis pergerakan stok (5.3), dan format *ledger* bertanda (`qty_change`). | Celah spesifikasi yang akan muncul saat implementasi. |
| 12 | Aturan penonaktifan master data, SKU tak berubah, `allow_decimal` pada UoM, tanpa *hard delete*. | `is_active` tanpa aturan bisa merusak ketertelusuran. |
| 13 | Out of scope diperluas: Goods Issue, retur/reversal, konversi UoM, penerimaan Transfer bertahap, persetujuan PO multi-level, UI. | Dibuat eksplisit agar MVP tetap fokus. |
| 14 | Kriteria penerimaan: AC-02 dan AC-03 disesuaikan alur `APPROVED`; ditambahkan AC-06 sampai AC-13. | Menguji konkurensi, atomisitas, imutabilitas, pembekuan, token, *scoping*, dan posting ganda. |
| 15 | Ditambahkan Lampiran A (entitas data), Lampiran B (konvensi API & kode error). | Landasan penulisan skema SQL dan implementasi API. |
| 16 | Ditambahkan tabel `menus` (`009_create_menu_tables.sql`) dan endpoint `/api/v1/menus` (termasuk `/menus/my-menu` berbasis `permission_id`). | Atas persetujuan pemilik proyek agar klien *frontend* dapat langsung menampilkan struktur menu navigasi dinamis dari database sesuai hak akses pengguna. |
| 17 | Diperjelas penyaringan pohon menu, operasi administrasi tanpa hard delete, audit log, endpoint menu, serta AC-14. | Menentukan perilaku yang dapat diuji untuk menu dinamis berbasis permission yang disetujui pemilik proyek. |

**Keputusan yang perlu dikonfirmasi pemilik produk:** (a) penambahan status `APPROVED` pada Transfer; (b) Goods Issue tetap di luar MVP sehingga stok hanya berkurang lewat Transfer dan Opname; (c) PO memiliki satu gudang tujuan per dokumen; (d) pembekuan lokasi selama Opname.
