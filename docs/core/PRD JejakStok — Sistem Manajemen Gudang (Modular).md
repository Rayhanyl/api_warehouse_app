# PRD JejakStok — Sistem Manajemen Gudang (Modular)

Oct 30, 2026 · @Rayhan yuda

## Tentang Dokumen

PRD ini menjadi acuan tunggal untuk apa yang dibangun JejakStok dan aturan bisnis yang mengikatnya, disusun per modul agar satu perubahan hanya menyentuh satu pemilik.

Isinya merapikan PRD v2.0 (`PRODUCT_REQUIREMENTS_DOCUMENT.MD`) tanpa mengubah aturan bisnisnya: setiap fitur, aturan, dan kriteria penerimaan diberi ID tetap dan tepat satu modul pemilik. Pemetaan ID lama ke ID baru ada di bagian Keterlacakan. Dua modul tambahan, Goods Issue dan Pelaporan, berstatus **Usulan** karena deskripsi proyek menyebut pengeluaran barang dan laporan, sedangkan v2.0 menempatkannya di luar MVP.

**Cara memakainya**

- Ingin tahu batas produk: baca Visi dan Ruang Lingkup.
- Mengubah atau menambah fitur: lompat ke bagian modul terkait, lalu ikuti prosedur perubahan di Standar Dokumentasi.
- Mengubah aturan yang dipakai banyak modul: ubah di Aturan Bisnis Global, jangan menyalinnya ke tiap modul.

**Dokumen terkait**

| Dokumen | Peran | Hubungan dengan PRD ini |
| --- | --- | --- |
| `SCHEMA_DATABASE.MD` | DDL dan migrasi PostgreSQL | Mengikuti PRD; pemilik tiap tabel ada di bagian Model Data |
| `PRD_FRONTEND.md` | Kebutuhan antarmuka React | Merujuk ID modul dan aturan; tidak menambah aturan bisnis |
| `FOLDER_STRUCTURE.md`, `FOLDER_STRUCTURE.MD` | Struktur folder dan arsitektur kode | Satu folder fitur per modul |
| `RULE_CREATE_API_DOKUMENTATION.MD` | Aturan menulis `docs/api/` | Satu berkas API per modul; bila kode aktual berbeda dari PRD, kode menang dan selisihnya dicatat |

## Visi, Tujuan, dan Ruang Lingkup

JejakStok membuat setiap perpindahan barang di gudang tercatat, dapat ditelusuri, dan akurat, dari penerimaan sampai penyesuaian stok. Produk ini berbentuk service REST API (Python, FastAPI, PostgreSQL tanpa ORM, JWT) yang dikonsumsi klien terpisah seperti frontend React, Swagger UI, atau Postman.

### Tujuan

| ID | Tujuan | Modul utama |
| --- | --- | --- |
| G-01 | Visibilitas stok multi-gudang: per gudang, per lokasi, agregat, dan stok dalam perjalanan | WHS, INV, TRF |
| G-02 | Penerimaan barang tervalidasi terhadap Purchase Order, termasuk pengiriman parsial | PUR, RCV |
| G-03 | Ketertelusuran penuh lewat ledger pergerakan stok dan audit log yang tidak dapat diubah | INV, AUD |
| G-04 | Integritas persediaan: tanpa stok negatif tidak sah, dengan rekonsiliasi fisik berkala | INV, OPN |
| G-05 | SaaS multi-tenant: banyak perusahaan memakai JejakStok dengan data terisolasi penuh, dan perilaku bisnis tiap tenant sama dengan v2.0 | TNT, CFG, IAM, PLT |
| G-06 | Dapat dipakai pada berbagai jenis gudang tanpa kode khusus industri; perbedaan perilaku diatur lewat konfigurasi | CFG, MST, WHS |

### Ukuran keberhasilan

| ID | Ukuran | Target | Sumber |
| --- | --- | --- | --- |
| SM-01 | `qty_after` baris ledger terakhir sama dengan `qty_on_hand` untuk setiap kombinasi gudang, lokasi, barang | 100% | INV-BR02 |
| SM-02 | Posting ganda dan penerimaan melebihi pesanan | 0 kejadian | AC-01, AC-13 |
| SM-03 | Waktu respons baca saldo stok dan pencarian master data (persentil ke-95) | di bawah 200 ms pada 20 pengguna bersamaan, 10.000 barang aktif, 1.000.000 baris ledger | NFR-03 |
| SM-04 | Kriteria penerimaan AC-01 sampai AC-21 lulus pada PostgreSQL sungguhan | 14 dari 14 | NFR-07 |

Ukuran bisnis seperti selisih opname atau lama proses penerimaan belum ditetapkan; lihat Pertanyaan Terbuka.

### Dalam ruang lingkup

Dua belas modul MVP: Platform (PLT), Identity dan Akses (IAM), Audit (AUD), Tenant (TNT), Konfigurasi (CFG), Master Data (MST), Gudang dan Lokasi (WHS), Inventory (INV), Purchase Order (PUR), Goods Receipt (RCV), Transfer Stok (TRF), dan Stock Opname (OPN). Dua modul berstatus Usulan: Goods Issue (ISS) dan Pelaporan (RPT).

### Di luar ruang lingkup MVP

Setiap butir di bawah punya ID agar keputusan memasukkannya kelak dapat ditelusuri ke modul yang terdampak.

| ID | Di luar lingkup | Perilaku pada MVP | Perkiraan modul terdampak bila masuk |
| --- | --- | --- | --- |
| OOS-01 | Lot/batch dan tanggal kedaluwarsa | Semua unit satu SKU dianggap homogen | MST, INV, RCV, TRF, OPN |
| OOS-02 | Nomor seri per unit | Identitas unit tidak dilacak | MST, INV, RCV, TRF, OPN |
| OOS-03 | Costing persediaan (FIFO, LIFO, FEFO, rata-rata tertimbang) | Hanya kuantitas fisik | MST, INV, RCV, RPT |
| OOS-04 | Reservasi stok | Stok berkurang hanya saat pengeluaran fisik dieksekusi | INV, TRF, ISS |
| OOS-05 | Goods Issue (pengeluaran ke pelanggan, produksi, pemakaian internal) | Stok berkurang hanya lewat pengiriman Transfer dan penyesuaian Opname negatif | Menjadi modul ISS (Usulan) |
| OOS-06 | Retur ke pemasok dan pembalikan dokumen | Koreksi GR yang salah lewat Stock Opname | PUR, RCV, INV |
| OOS-07 | Konversi satuan | Satu UoM dasar per barang | MST, PUR, RCV, TRF, OPN |
| OOS-08 | Penerimaan Transfer bertahap | Penerimaan Transfer final satu kali per dokumen | TRF |
| OOS-09 | Persetujuan PO berjenjang | Penerbitan oleh pengguna berwenang dianggap persetujuan | PUR, IAM |
| OOS-10 | Antarmuka pengguna di dalam service, notifikasi email atau WhatsApp, integrasi ERP atau barcode | API menyediakan metadata menu; UI dibangun terpisah (`PRD_FRONTEND.md`) | IAM, RCV, TRF, OPN |
| OOS-11 | Penagihan dan pembayaran langganan | Paket dan batas diatur manual oleh Platform Admin | TNT, modul baru BIL |
| OOS-12 | Pendaftaran mandiri tenant | Tenant dibuat oleh Platform Admin (OQ-13) | TNT |
| OOS-13 | Single sign-on (SAML, OIDC) dan 2FA per tenant | Login dengan slug, username, dan kata sandi | IAM |
| OOS-14 | Domain khusus dan white-label per tenant | Satu domain; tenant dikenali lewat slug | TNT, CFG |
| OOS-15 | Satu pengguna di beberapa tenant | Satu akun milik satu tenant (OQ-14) | IAM, TNT |
| OOS-16 | Database atau skema terpisah per tenant, dan penempatan data per wilayah | Satu database bersama dengan isolasi baris (OQ-11) | PLT, TNT |

## Pengguna dan Peran

Akses diatur oleh lima peran bawaan dan cakupan gudang; setiap kode permission dimiliki satu modul, sehingga modul baru menambah baris sendiri tanpa menyentuh modul lain.

| Peran | Siapa | Fokus kerja |
| --- | --- | --- |
| Super Admin | Administrator sistem TI | Pengguna, role, penugasan gudang, konfigurasi gudang, Audit Log; akses ke semua gudang |
| Warehouse Manager | Kepala operasional gudang | Lokasi, persetujuan Transfer dan Opname, penutupan PO, pemantauan stok |
| Purchasing Staff | Staf pengadaan | Master barang dan pemasok, siklus PO |
| Warehouse Staff | Operator gudang | GR, Transfer fisik, hitung fisik Opname, hanya pada gudang yang ditugaskan |
| Auditor | Pemeriksa internal atau manajemen | Akses baca ke master, dokumen, stok, ledger, dan Audit Log |

Nama resmi peran adalah **Auditor**. Judul "Auditor / Viewer" di v2.0 tidak dipakai lagi, mengikuti data seed dan `PRD_FRONTEND.md`.

### Matriks permission

Tanda **(g)** berarti hanya berlaku pada gudang yang ditugaskan ke pengguna (aturan IAM-BR13). Kode di kolom pertama adalah identitas izin di tabel `permissions` dan tidak boleh diganti nama.

| Permission | Modul pemilik | Super Admin | Warehouse Manager | Purchasing Staff | Warehouse Staff | Auditor |
| --- | --- | :-: | :-: | :-: | :-: | :-: |
| `user:manage` | IAM | ✓ | – | – | – | – |
| `warehouse:manage` | WHS | ✓ | – | – | – | – |
| `location:manage` | WHS | ✓ | ✓ (g) | – | – | – |
| `master:manage` | MST | ✓ | – | ✓ | – | – |
| `master:read` | MST | ✓ | ✓ | ✓ | ✓ | ✓ |
| `po:create` | PUR | ✓ | – | ✓ | – | – |
| `po:issue` | PUR | ✓ | – | ✓ | – | – |
| `po:cancel` | PUR | ✓ | – | ✓ | – | – |
| `po:close` | PUR | ✓ | ✓ | ✓ | – | – |
| `po:read` | PUR | ✓ | ✓ | ✓ | ✓ | ✓ |
| `gr:manage` | RCV | ✓ | – | – | ✓ (g) | – |
| `gr:read` | RCV | ✓ | ✓ | ✓ | ✓ (g) | ✓ |
| `transfer:create` | TRF | ✓ | – | – | ✓ (g) | – |
| `transfer:approve` | TRF | ✓ | ✓ (g) | – | – | – |
| `transfer:ship` | TRF | ✓ | – | – | ✓ (g) | – |
| `transfer:receive` | TRF | ✓ | – | – | ✓ (g) | – |
| `transfer:read` | TRF | ✓ | ✓ | – | ✓ (g) | ✓ |
| `opname:manage` | OPN | ✓ | ✓ (g) | – | – | – |
| `opname:count` | OPN | ✓ | – | – | ✓ (g) | – |
| `opname:approve` | OPN | ✓ | ✓ (g) | – | – | – |
| `opname:read` | OPN | ✓ | ✓ | – | ✓ (g) | ✓ |
| `stock:read` | INV | ✓ | ✓ | ✓ | ✓ (g) | ✓ |
| `ledger:read` | INV | ✓ | ✓ | – | ✓ (g) | ✓ |
| `audit:read` | AUD | ✓ | – | – | – | ✓ |
| `tenant:read` | TNT | ✓ | – | – | – | – |
| `tenant:update` | TNT | ✓ | – | – | – | – |
| `settings:read` | CFG | ✓ | ✓ | – | – | ✓ |
| `settings:manage` | CFG | ✓ | ✓ (g) | – | – | – |

Pengguna terautentikasi tanpa permission khusus tetap dapat melihat profil sendiri, mengambil pohon menu sesuai hak aksesnya, dan mengganti kata sandinya sendiri.

### Peran per tenant dan Platform Admin

Sejak v3.1 setiap peran, pengguna, dan penugasan gudang milik satu tenant. Lima peran di atas adalah peran bawaan yang disalin ke setiap tenant baru; Super Admin berarti administrator tenant itu sendiri, bukan operator platform. Operator JejakStok memakai peran terpisah, Platform Admin, yang tidak ada di matriks tenant dan tidak melihat stok atau dokumen tenant (TNT-BR06).

| Permission platform | Modul pemilik | Platform Admin |
| --- | --- | --- |
| `platform:tenant_read` | TNT | ✓ |
| `platform:tenant_manage` | TNT | ✓ |

Registri permission berisi 28 kode tenant dan 2 kode platform.

## Arsitektur Modular

Sistem terdiri dari dua belas modul MVP dan dua modul usulan; tiap modul memiliki tabel, aturan, dan permission sendiri, dan hanya berbicara dengan modul lain lewat kontrak yang tercatat di bagian ini.

&#91;embedded content: peta dependensi modul · 5 dependensi tulis, tanpa siklus\]

Panah penuh menunjukkan siapa menulis ke siapa dan hanya bergerak ke arah INV dan PUR. Pembacaan dan panggilan lintas-lapisan tidak mengubah data pemilik, jadi tidak membentuk siklus. RPT (usulan) hanya membaca sehingga tidak digambar. TNT menulis ke IAM dan CFG hanya saat pendaftaran tenant dan tidak ada tulisan balik ke TNT, jadi graf tulis tetap tanpa siklus; ketiganya tidak menyentuh stok sehingga tidak digambar.

### Katalog modul

| Kode | Modul | Tanggung jawab | Tabel yang dimiliki | Status |
| --- | --- | --- | --- | --- |
| PLT | Platform | Penomoran dokumen, pagination, format error, request id, health, migrasi skema | `document_sequences`, `schema_migrations` | MVP |
| IAM | Identity dan Akses | Autentikasi, token, RBAC, pengguna, penugasan gudang, menu navigasi | `roles`, `permissions`, `role_permissions`, `users`, `user_warehouses`, `refresh_tokens`, `menus` | MVP |
| AUD | Audit | Pencatatan dan pembacaan jejak audit | `audit_logs` | MVP |
| MST | Master Data | Kategori, satuan (UoM), barang, pemasok | `categories`, `uoms`, `items`, `suppliers` | MVP |
| WHS | Gudang dan Lokasi | Gudang, pengaturan stok negatif, lokasi penyimpanan | `warehouses`, `storage_locations` | MVP |
| INV | Inventory | Saldo stok, ledger, satu-satunya pintu perubahan stok, tampilan stok | `inventory_balances`, `stock_movements` | MVP |
| PUR | Purchase Order | PO, siklus status, pelacakan pemenuhan | `purchase_orders`, `po_lines` | MVP |
| RCV | Goods Receipt | Penerimaan barang parsial dan posting atomik | `goods_receipts`, `gr_lines` | MVP |
| TRF | Transfer Stok | Transfer dua tahap, selisih penerimaan, stok dalam perjalanan | `stock_transfers`, `stock_transfer_lines` | MVP |
| OPN | Stock Opname | Hitung fisik, pembekuan lokasi, penyesuaian, saldo awal | `stock_opnames`, `stock_opname_lines` | MVP |
| ISS | Goods Issue | Pengeluaran barang | Belum ditetapkan | Usulan |
| RPT | Pelaporan | Laporan baca-saja atas data modul lain | Tidak punya tabel | Usulan |
| TNT | Tenant | Tenant (perusahaan pelanggan), siklus hidup, paket dan batas pemakaian, pendaftaran, operasi platform | `tenants`, `plans`, `platform_admins` | MVP |
| CFG | Konfigurasi | Pengaturan bertingkat (bawaan, tenant, gudang), label dan lokal tampilan, registri kunci pengaturan | `settings` | MVP |

### Kontrak antarmodul

Kontrak adalah satu-satunya jalur interaksi antarmodul. Kolom **Jenis** membedakan kontrak tulis (mengubah data pemilik), baca (hanya membaca), dan lintas-lapisan (boleh dipanggil semua modul).

| Kontrak | Pemilik | Pemanggil | Jenis | Perilaku |
| --- | --- | --- | --- | --- |
| `authorize(user, permission, warehouse?)` | IAM | Semua modul | Lintas-lapisan | Memeriksa permission dan penugasan gudang (`require_permission`, `ensure_warehouse_access`) |
| `record(action, entity, old, new)` | AUD | Semua modul yang mengubah data | Lintas-lapisan | Menulis audit log dalam transaksi yang sama dengan perubahannya |
| `next_number(doc_type)` | PLT | PUR, RCV, TRF, OPN | Tulis | Nomor dokumen atomik per jenis dan periode |
| `apply_movement(...)` | INV | RCV, TRF, OPN | Tulis | Satu-satunya jalan mengubah saldo dan menulis ledger |
| `apply_receipt(po_line, qty)` | PUR | RCV | Tulis | Menambah `qty_received` dan mengevaluasi ulang status PO |
| `is_location_frozen(warehouse, location)` | OPN | INV | Baca | Menyatakan lokasi sedang dibekukan sesi Opname |
| `gr_status_summary(po)` | RCV | PUR | Baca | Jumlah GR `DRAFT` dan `POSTED` pada sebuah PO |
| `in_transit(filter)` | TRF | INV | Baca | Kuantitas Transfer berstatus `SHIPPED` yang belum `RECEIVED` |
| `validate_location(warehouse, location)` | WHS | INV, RCV, TRF, OPN | Baca | Lokasi aktif dan milik gudang yang dirujuk (`INVALID_LOCATION`) |
| `open_references(entity)` | INV, PUR, RCV, TRF, OPN (masing-masing untuk datanya) | MST, WHS | Baca | Menyatakan apakah entitas masih bersaldo tidak nol atau dirujuk dokumen non-final (GBR-13) |
| `current_tenant()` | PLT | Semua modul | Lintas-lapisan | Mengembalikan tenant\_id dari token terautentikasi dan mengikatnya ke transaksi database agar RLS berlaku (GBR-16, GBR-17) |
| `tenant_status(tenant)` | TNT | IAM | Baca | Status dan paket tenant; diperiksa saat login, refresh, dan setiap request (TENANT\_SUSPENDED) |
| `check_quota(resource)` | TNT | MST, WHS, IAM | Baca | Menyatakan apakah batas paket untuk gudang, pengguna aktif, atau barang aktif masih tersedia (TENANT\_LIMIT\_EXCEEDED) |
| `provision_tenant_access(tenant, admin)` | IAM | TNT | Tulis | Menyalin lima peran bawaan beserta pemetaan permission ke tenant baru dan membuat Super Admin pertama |
| `seed_tenant_settings(tenant)` | CFG | TNT | Tulis | Menyiapkan nilai tingkat tenant dari bawaan registri kunci pengaturan |
| `get_setting(key, warehouse?)` | CFG | Semua modul | Baca | Nilai efektif dengan urutan gudang, tenant, lalu bawaan registri (CFG-BR01) |

### Aturan batas modul

1. **BND-01 Satu pemilik.** Tabel, aturan bisnis, permission, kode error, tipe pergerakan, dan prefix nomor dokumen dimiliki tepat satu modul. Modul lain merujuk ID-nya dan tidak menyalin isinya.
2. **BND-02 Tulis lewat pemilik.** Data milik modul lain hanya diubah lewat kontrak tulis di atas. Perubahan stok tanpa `apply_movement` dilarang.
3. **BND-03 Tanpa siklus tulis.** Dependensi tulis harus membentuk graf tanpa siklus. Dependensi baca boleh dua arah, tetapi hanya lewat kontrak baca yang diterbitkan pemilik.
4. **BND-04 Satu modul, satu set berkas.** Tiap modul memiliki route, service, repository, schema, dan migrasi sendiri; peta kodenya tercantum di spesifikasi modul.
5. **BND-05 Penambahan murni.** Modul atau fitur baru hanya boleh menambah tabel, baris registri, dan kontrak baru. Mengubah perilaku kontrak yang sudah ada tergolong perubahan besar dan mengikuti prosedur perubahan.
6. **BND-06 Registri bersama.** Enam registri diisi banyak modul tetapi hanya punya satu tabel resmi: permission (bagian Pengguna dan Peran), tipe pergerakan (INV), prefix nomor dokumen (PLT), status non-final (Aturan Bisnis Global), kode error (Aturan Bisnis Global), dan kunci pengaturan (CFG).
7. **BND-07 Isolasi tenant.** Tenant adalah batas isolasi tertinggi. Klien tidak pernah mengirim tenant\_id; konteks tenant diberikan PLT lewat current\_tenant dan ditegakkan oleh filter query, kunci asing komposit, dan RLS. Tidak ada kontrak yang melintasi tenant, kecuali operasi platform milik TNT.
8. **BND-08 Konfigurasi, bukan percabangan.** Perbedaan perilaku antar-industri, tenant, atau gudang diwujudkan sebagai kunci pengaturan terdaftar di CFG dan dibaca lewat get\_setting. Modul tidak boleh memuat percabangan kode untuk tenant atau industri tertentu.

### Dampak multi-tenant pada modul

Keputusan SaaS multi-tenant (2026-11-02) menambah kolom dan batasan pada tabel yang sudah ada tanpa mengubah perilaku bisnis v2.0 di dalam satu tenant. Data dari instalasi satu organisasi dimigrasikan sebagai satu tenant bawaan.

| Modul | Perubahan | Aturan terkait |
| --- | --- | --- |
| PLT | `current_tenant` mengikat tenant ke transaksi dan mengaktifkan RLS; kunci `document_sequences` menjadi `(tenant_id, doc_type, periode)` | GBR-16, GBR-17, GBR-18 |
| IAM | `roles`, `role_permissions`, `users`, `user_warehouses`, `refresh_tokens` menjadi per tenant; `permissions` dan `menus` tetap global; token memuat `tenant_id`; login memakai slug tenant | IAM-BR16 sampai IAM-BR20 |
| AUD | `audit_logs` memuat `tenant_id`; pembacaan hanya untuk tenant sendiri; operasi platform dicatat dengan tenant sasaran | GBR-16, TNT-BR07 |
| MST, WHS | Semua tabel menjadi per tenant; SKU, kode kategori, kode pemasok, kode gudang, dan kode lokasi unik per tenant; kuota gudang dan barang aktif | GBR-18, TNT-BR05 |
| INV | `inventory_balances` dan `stock_movements` memuat `tenant_id`; kunci saldo menjadi `(tenant_id, warehouse_id, location_id, item_id)`; urutan penguncian GBR-07 dan sifat append-only tidak berubah | GBR-02, GBR-07, GBR-16 |
| PUR, RCV, TRF, OPN | Tabel dokumen per tenant dengan kunci asing komposit; nomor dokumen per tenant | GBR-16, GBR-18 |
| ISS, RPT (usulan) | Mengikuti GBR-16 sejak desain; laporan hanya melintasi gudang dalam satu tenant | BND-07 |

## Standar Dokumentasi

Setiap hal yang bisa berubah punya ID permanen, satu pemilik, dan satu tempat di dokumen ini; perubahan mengikuti prosedur lima langkah di bawah.

### Skema ID

| Jenis | Format | Contoh |
| --- | --- | --- |
| Modul | Tiga huruf kapital | `INV` |
| Fitur | `<MOD>-F##` | `RCV-F02` |
| Aturan bisnis modul | `<MOD>-BR##` | `INV-BR03` |
| Aturan bisnis global | `GBR-##` | `GBR-03` |
| Aturan batas modul | `BND-##` | `BND-02` |
| Kriteria penerimaan | `AC-##` (ID v2.0 dipertahankan) | `AC-06` |
| Kebutuhan non-fungsional | `NFR-##` | `NFR-03` |
| Tujuan, ukuran, di luar lingkup, pertanyaan terbuka, risiko | `G-##`, `SM-##`, `OOS-##`, `OQ-##`, `RSK-##` | `OOS-05` |

Aturan pemakaian ID:

- ID tidak pernah dipakai ulang. Butir yang dihapus berstatus Dipensiunkan dan tetap tercatat; nomor boleh berlubang.
- Identifier teknis yang sudah dipakai kode, test, atau dokumen lain tidak diganti: kode permission, kode error, nilai status, tipe pergerakan, dan `AC-##`. Nama fungsi test memuat kode AC-nya, jadi mengganti nomor AC akan memutus penelusuran.
- Dokumen lain merujuk ID, bukan nomor bagian. Nomor bagian di PRD v2.0 tidak lagi berlaku; pemetaannya ada di Keterlacakan.

### Template spesifikasi modul

Setiap modul di bagian Spesifikasi Modul memakai kerangka yang sama, dengan urutan yang sama, agar pembaca selalu tahu di mana mencari sesuatu.

```markdown
### <KODE> — <Nama modul>

<Satu kalimat: apa yang dimiliki dan dijamin modul ini>

| Atribut | Isi |
| Versi modul / Status | 1.0 · MVP atau Usulan |
| Asal v2.0 | FR, bagian, dan AC yang dipindahkan |
| Peta kode | route, service, repository, schema, migrasi |
| Bergantung pada | kontrak tulis dan baca yang dipanggil |
| Dipakai oleh | modul yang memanggil kontrak modul ini |

**Fitur** — ID, deskripsi, prioritas
**Aturan bisnis** — ID, aturan yang dapat diuji
**Status dan transisi** — hanya bila ada siklus status
**Permission dan API** — kode permission milik modul, endpoint
**Kriteria penerimaan** — AC yang dimiliki modul
**Titik perluasan** — apa yang boleh ditambah tanpa menyentuh modul lain
```

Status butir: Usulan, Disetujui, Diimplementasi, Dipensiunkan. Prioritas: P0 wajib untuk MVP, P1 penting setelah alur inti stabil.

Versi modul memakai `MAJOR.MINOR`. MINOR naik bila fitur atau aturan ditambah tanpa mengubah yang sudah ada. MAJOR naik bila perilaku aturan atau kontrak yang sudah ada berubah.

### Prosedur perubahan

1. **Cari pemilik.** Temukan ID aturan atau fitur yang terkena. Bila tidak ada pemiliknya, putuskan apakah itu perluasan modul yang ada atau modul baru.
2. **Telusuri dampak.** Lihat baris Dipakai oleh dan tabel kontrak, lalu jalankan daftar periksa dampak di bawah.
3. **Ubah hanya di modul pemilik.** Modul terdampak cukup diberi rujukan ke ID, bukan salinan teks.
4. **Catat.** Tambahkan baris di Change Log, perbarui Keterlacakan, dan naikkan versi modul.
5. **Sinkronkan turunan.** Perbarui `SCHEMA_DATABASE.MD`, `docs/api/`, dan `PRD_FRONTEND.md`. Selisih antara PRD dan kode yang belum terselesaikan ditandai Perlu Ditinjau sesuai `RULE_CREATE_API_DOKUMENTATION.MD`.

### Daftar periksa dampak

| Bila yang berubah | Periksa juga |
| --- | --- |
| Status dokumen baru | Tabel transisi modul, `CHECK` status di skema, registri status non-final, tampilan status di frontend |
| Tipe pergerakan baru | Registri tipe pergerakan INV; `CHECK` `movement_type`, `reference_type`, arah tanda, dan pasangan tipe-referensi pada `stock_movements` |
| Jenis dokumen baru | Prefix di PLT dan `CHECK` `doc_type` pada `document_sequences` |
| Permission baru | Matriks permission, migrasi seed baru (migrasi bersifat forward-only), `permission_id` menu terkait |
| Kode error baru atau berubah | Katalog error, pemetaan pesan di frontend |
| Menu baru | Migrasi data menu baru dan rute frontend yang sesuai |
| Aturan penonaktifan entitas | Registri status non-final dan pesan `ENTITY_IN_USE` |

## Aturan Bisnis Global

Delapan belas aturan berlaku untuk semua modul; ubah di sini sekali, jangan menyalinnya ke tiap modul. Spesifikasi modul hanya merujuk ID-nya.

| ID | Aturan | Asal v2.0 | Ditegakkan oleh |
| --- | --- | --- | --- |
| GBR-01 | Tidak ada penghapusan permanen pada master data maupun dokumen transaksi; penonaktifan memakai `is_active` | FR-02 | Semua modul pemilik data |
| GBR-02 | `stock_movements` dan `audit_logs` bersifat append-only. Aplikasi dan database menolak `UPDATE` dan `DELETE` (trigger, serta hak `UPDATE`, `DELETE`, `TRUNCATE` dicabut dari role `wms_app`). Koreksi dilakukan dengan baris baru | 6.4 | INV, AUD |
| GBR-03 | Satu aksi bisnis adalah satu transaksi database yang mencakup status dokumen, saldo, ledger, dan audit log; bila satu langkah gagal, semuanya dibatalkan. Batas transaksi ada di service use case | 7.1 | Semua modul |
| GBR-04 | Status berubah hanya lewat endpoint aksi khusus. Transisi di luar tabel transisi modul ditolak 409 `INVALID_STATE_TRANSITION`; bila dua permintaan memproses dokumen yang sama bersamaan, hanya satu yang berhasil | 5.1, 6.5 | Semua modul dokumen |
| GBR-05 | Kuantitas disimpan `NUMERIC(18,4)`, maksimum 4 desimal, dikirim sebagai string desimal di JSON. Baris dokumen harus lebih dari 0, kecuali `qty_physical` Opname dan `qty_received` Transfer yang boleh 0. Barang ber-UoM `allow_decimal = FALSE` harus bilangan bulat | 6.9, 7.4 | MST, INV, semua modul dokumen |
| GBR-06 | Perubahan saldo stok hanya lewat `apply_movement` milik INV | FR-08 | INV |
| GBR-07 | Urutan penguncian seragam: (1) header dokumen, (2) PO terkait, (3) lokasi (`FOR SHARE`, atau `FOR UPDATE` saat Opname dimulai) berurut `id`, (4) saldo berurut `(warehouse_id, location_id, item_id)`. Baris saldo yang belum ada dibuat dengan upsert sebelum dikunci | 6.5 | Semua modul yang mengubah stok |
| GBR-08 | Nomor dokumen berformat `{PREFIX}-{YYYYMM}-{NNNN}`, dibuat server, di-reset tiap bulan, aman terhadap akses bersamaan; nomor dokumen yang dibatalkan tidak dipakai ulang | FR-10 | PLT |
| GBR-09 | Endpoint daftar memakai `limit` (bawaan 50, maksimum 200), `offset`, dan pengurutan dari daftar kolom yang diizinkan. Pembacaan ledger wajib dipaginasi dan mendukung filter rentang tanggal | FR-11 | PLT |
| GBR-10 | Otorisasi dua lapis: permission peran, lalu cakupan gudang pada data. Server adalah otoritas akhir; menu atau UI hanya petunjuk | 3, 3.2 | IAM |
| GBR-11 | Gudang, barang, pemasok, dan lokasi pada dokumen baru harus aktif, dan lokasi harus milik gudang yang dirujuk | 6.3 | MST, WHS, modul dokumen |
| GBR-12 | Kata sandi, hash kata sandi, dan token tidak boleh muncul di audit log, log aplikasi, maupun response error | FR-09, 7.2 | AUD, IAM |
| GBR-13 | Gudang, lokasi, dan barang tidak dapat dinonaktifkan bila masih bersaldo tidak nol atau dipakai dokumen non-final; pemasok tidak dapat dinonaktifkan bila masih punya PO non-final. Ditolak 409 `ENTITY_IN_USE` | 6.8 | MST, WHS |
| GBR-14 | Waktu disimpan sebagai `TIMESTAMPTZ` UTC dan dikirim ISO 8601; tanggal dokumen berformat `YYYY-MM-DD` | 7.5, Lampiran B | Semua modul |
| GBR-15 | Error berbentuk `{ "error": { "code", "message", "details" } }`; setiap kode error dimiliki satu modul pada katalog di bawah | Lampiran B | PLT |
| GBR-16 | Setiap tabel milik tenant memiliki kolom `tenant_id` NOT NULL, dan setiap query hanya membaca atau menulis baris tenant pemanggil. Kunci asing antar-tabel milik tenant bersifat komposit `(tenant_id, id)` sehingga satu tenant tidak dapat merujuk baris tenant lain. Database menegakkannya sekali lagi dengan Row Level Security | Baru v3.1 | Semua modul pemilik data, PLT |
| GBR-17 | `tenant_id` hanya berasal dari token terautentikasi, tidak pernah dari body, query, atau path. Akses ke data tenant lain dijawab 404 `NOT_FOUND`, bukan 403, agar keberadaan data tidak bocor. Tenant yang ditangguhkan ditolak 403 `TENANT_SUSPENDED` | Baru v3.1 | IAM, PLT, TNT |
| GBR-18 | Semua keunikan bisnis (SKU, kode gudang, kode lokasi, nomor dokumen, username) berlaku per tenant, bukan global. Penomoran dokumen (GBR-08) berjalan terpisah untuk tiap tenant. Satu-satunya keunikan global adalah slug tenant | Baru v3.1 | Semua modul, PLT, TNT |

### Registri status non-final

GBR-13 membaca tabel ini. Modul dokumen baru wajib menambahkan barisnya; tanpa itu, penonaktifan entitas yang dipakai dokumen tersebut tidak akan terdeteksi.

| Modul | Dokumen | Status non-final | Status final |
| --- | --- | --- | --- |
| PUR | Purchase Order | `DRAFT`, `ISSUED`, `PARTIALLY_RECEIVED` | `RECEIVED`, `CLOSED`, `CANCELLED` |
| RCV | Goods Receipt | `DRAFT` | `POSTED`, `CANCELLED` |
| TRF | Transfer Stok | `DRAFT`, `APPROVED`, `SHIPPED` | `RECEIVED`, `CANCELLED` |
| OPN | Stock Opname | `DRAFT`, `IN_PROGRESS`, `WAITING_APPROVAL` | `COMPLETED`, `CANCELLED` |

### Katalog kode error

| Kode | HTTP | Kondisi | Pemilik |
| --- | :-: | --- | --- |
| `AUTH_INVALID_CREDENTIALS` | 401 | Username atau kata sandi salah | IAM |
| `AUTH_TOKEN_INVALID` | 401 | Token tidak valid, kedaluwarsa, atau sudah dicabut | IAM |
| `AUTH_TOO_MANY_ATTEMPTS` | 429 | Akun terkunci sementara akibat login gagal berulang | IAM |
| `PERMISSION_DENIED` | 403 | Pengguna tidak memiliki permission yang dibutuhkan | IAM |
| `WAREHOUSE_NOT_ASSIGNED` | 403 | Pengguna tidak ditugaskan pada gudang terkait | IAM |
| `NOT_FOUND` | 404 | Data tidak ditemukan | PLT |
| `VALIDATION_ERROR` | 422 | Payload tidak valid, termasuk alasan selisih atau penolakan yang kosong | PLT |
| `INACTIVE_REFERENCE` | 422 | Gudang, barang, atau pemasok yang dirujuk tidak aktif | PLT |
| `DUPLICATE` | 409 | Pelanggaran keunikan (SKU, kode, nomor dokumen) | PLT |
| `INVALID_STATE_TRANSITION` | 409 | Transisi status tidak diizinkan atau dokumen sudah diproses | PLT |
| `ENTITY_IN_USE` | 409 | Penonaktifan ditolak karena masih dipakai atau bersaldo | PLT |
| `INVALID_LOCATION` | 422 | Lokasi tidak aktif atau bukan milik gudang yang dipilih | WHS |
| `INSUFFICIENT_STOCK` | 409 | Stok tidak mencukupi | INV |
| `LOCATION_FROZEN` | 409 | Lokasi sedang dibekukan oleh Stock Opname | INV |
| `OVER_RECEIPT` | 409 | Penerimaan melebihi kuantitas pesanan PO | RCV |
| `TRANSFER_QTY_EXCEEDS_SHIPPED` | 409 | `qty_received` melebihi kuantitas yang dikirim | TRF |
| `INTERNAL_ERROR` | 500 | Kesalahan internal. **Perlu Ditinjau:** disebut di `PRD_FRONTEND.md`, belum ada di katalog v2.0 | PLT |
| `TENANT_SUSPENDED` | 403 | Tenant ditangguhkan atau dinonaktifkan | TNT |
| `TENANT_LIMIT_EXCEEDED` | 409 | Batas paket tenant terlampaui (gudang, pengguna aktif, atau barang aktif) | TNT |
| `SETTING_INVALID` | 422 | Kunci pengaturan tidak terdaftar, di luar tingkat yang diizinkan, atau nilainya di luar jenis dan rentang | CFG |

## Spesifikasi Modul

Modul disusun dari fondasi ke atas mengikuti urutan dependensi. Setiap modul memakai template yang sama dan hanya memuat aturan miliknya; aturan lintas modul dirujuk lewat ID `GBR`.

### PLT — Platform

PLT menyediakan layanan teknis bersama yang tidak mengenal bisnis gudang: penomoran dokumen, pagination, penerjemahan error, dan jejak operasional.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-10, FR-11, bagian 7.5 dan 7.6, Lampiran B |
| Peta kode | `core/` (config, database, exceptions, logging, middleware), `utils/pagination.py`, `services/numbering_service.py`, `repositories/sequence_repo.py`, `db/migrate.py`, migrasi 006 (bagian `document_sequences`) |
| Bergantung pada | Tidak ada |
| Dipakai oleh | Semua modul |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| PLT-F01 | Penomoran dokumen atomik per jenis dan bulan | P0 | FR-10 |
| PLT-F02 | Pagination, pengurutan, dan filter standar untuk endpoint daftar | P0 | FR-11 |
| PLT-F03 | Penerjemahan error domain ke format error seragam | P0 | Lampiran B |
| PLT-F04 | Request id `X-Request-ID`, log terstruktur, dan `GET /health` | P0 | 7.6 |
| PLT-F05 | Migrasi skema `.sql` berurutan dengan pencatat versi | P0 | 7.5 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| PLT-BR01 | Jenis dokumen hanya boleh memakai prefix yang terdaftar pada registri di bawah. Jenis baru wajib mendaftarkan prefix dan memperbarui `CHECK` `doc_type` pada `document_sequences` | FR-10 |
| PLT-BR02 | Nomor berikutnya diambil dengan upsert atomik pada `document_sequences` (`INSERT ... ON CONFLICT DO UPDATE ... RETURNING`), sehingga dua permintaan bersamaan tidak mendapat nomor sama. Contoh: `PO-202610-0001` | FR-10 |
| PLT-BR03 | Berkas migrasi bernama `NNN_deskripsi.sql`, bersifat forward-only, dan berkas yang sudah diterapkan tidak pernah diubah; perubahan baru adalah berkas baru. Migrasi dijalankan role pemilik skema `wms_owner`, aplikasi berjalan dengan role `wms_app` | 7.5 |
| PLT-BR04 | Nama constraint dan indeks: `pk_`, `fk_`, `uq_`, `ck_`, `ix_`. Kunci utama memakai `BIGINT GENERATED ALWAYS AS IDENTITY` | 7.5 |
| PLT-BR05 | Setiap request membawa request id; bila klien tidak mengirim, server membuatnya dan mengembalikannya pada header respons | 7.6 |

**Registri prefix nomor dokumen**

| Prefix | Dokumen | Modul |
| --- | --- | --- |
| `PO` | Purchase Order | PUR |
| `GR` | Goods Receipt | RCV |
| `TRF` | Transfer Stok | TRF |
| `OPN` | Stock Opname | OPN |

**Permission dan API**

- Tidak memiliki permission. `GET /health` dan `GET /api/v1/health` tanpa autentikasi; base path domain adalah `/api/v1`.

**Kriteria penerimaan**

- Tidak ada AC tersendiri; perilaku PLT diuji lewat AC modul pemakainya.

**Titik perluasan**

- Jenis dokumen baru cukup menambah baris pada registri prefix dan migrasi `CHECK` baru; tidak ada modul lain yang berubah.

### IAM — Identity dan Akses

IAM memastikan hanya pengguna sah yang bertindak, dengan hak yang tepat, pada gudang yang tepat.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-01, bagian 3, 3.1, 3.2; AC-05 (sisi RBAC), AC-11, AC-12, AC-14; IAM-F10 sampai IAM-F12 dan IAM-BR16 sampai IAM-BR20 baru di v3.1 |
| Peta kode | `api/routes/auth.py`, `users.py`, `menus.py`, `api/deps.py`, `core/security.py`, `core/permissions.py`, `services/auth_service.py`, `user_service.py`, `menu_service.py`, `access_service.py`, `repositories/user_repo.py`, `token_repo.py`, `permission_repo.py`, `menu_repo.py`, migrasi 001, 008, 009 |
| Bergantung pada | Baca: WHS (gudang yang ditugaskan harus ada) dan TNT (tenant\_status). Lintas-lapisan: current\_tenant milik PLT. Lintas-lapisan: `record` milik AUD |
| Dipakai oleh | TNT (provision\_tenant\_access); semua modul, lewat kontrak `authorize` |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| IAM-F01 | Login dan penerbitan token | P0 | FR-01 |
| IAM-F02 | Refresh token berotasi dengan deteksi pemakaian ulang | P0 | FR-01 |
| IAM-F03 | Logout dan pencabutan sesi | P0 | FR-01 |
| IAM-F04 | Penguncian akun setelah login gagal berulang | P0 | FR-01 |
| IAM-F05 | RBAC: role, permission, pemeriksaan pada setiap request | P0 | 3, 3.1 |
| IAM-F06 | Manajemen pengguna, role, dan permission | P0 | 3 |
| IAM-F07 | Penugasan gudang (warehouse scoping) | P0 | 3.2 |
| IAM-F08 | Menu navigasi dinamis berbasis permission dan administrasinya | P0 | FR-01 |
| IAM-F09 | Profil sendiri dan penggantian kata sandi | P0 | 3.1 |
| IAM-F10 | Peran, pengguna, dan penugasan gudang per tenant | P0 | Baru v3.1 |
| IAM-F11 | Login dengan slug tenant dan token yang memuat tenant | P0 | Baru v3.1 |
| IAM-F12 | Penyediaan akses tenant baru: peran bawaan dan Super Admin pertama | P0 | Baru v3.1 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| IAM-BR01 | Access token JWT berumur 15 menit, memuat minimal `sub`, `jti`, `iat`, `exp`, ditandatangani HS256 dengan kunci dari variabel lingkungan (minimal 32 byte) | FR-01, 7.2 |
| IAM-BR02 | Peran dan status aktif pengguna diverifikasi dari database pada setiap request, sehingga perubahan peran atau penonaktifan berlaku seketika | FR-01 |
| IAM-BR03 | Refresh token berupa string acak opak berumur 7 hari, disimpan hanya sebagai hash, dan dirotasi pada setiap pemakaian; token lama berstatus revoked | FR-01 |
| IAM-BR04 | Pemakaian ulang refresh token yang sudah revoked dianggap indikasi pencurian: seluruh refresh token aktif pengguna dicabut dan kejadian dicatat di audit log (401) | FR-01, AC-11 |
| IAM-BR05 | Logout mencabut refresh token yang dipakai. Penonaktifan pengguna dan penggantian kata sandi mencabut seluruh refresh token pengguna | FR-01 |
| IAM-BR06 | Lima kali gagal login berturut-turut mengunci akun 15 menit; setiap kegagalan dicatat di audit log | FR-01 |
| IAM-BR07 | Semua endpoint kecuali `login`, `refresh`, dan `health` wajib Bearer token. Endpoint operasional dan admin juga memeriksa permission; profil sendiri dan menu sendiri cukup autentikasi | FR-01 |
| IAM-BR08 | Kata sandi di-hash dengan Argon2id (atau bcrypt), minimal 8 karakter | 7.2 |
| IAM-BR09 | `GET /menus/my-menu` mengembalikan pohon menu aktif terurut `sort_order` lalu `id`. Menu ber-`permission_id` tampil hanya bila pengguna memiliki permission itu; menu induk tanpa permission tampil bila punya anak yang terlihat; menu mandiri tanpa permission tampil bagi semua pengguna terautentikasi | FR-01, AC-14 |
| IAM-BR10 | Administrasi menu (lihat, buat, ubah, nonaktifkan) memerlukan `user:manage`; tidak ada hapus permanen; perubahan dicatat di audit log | FR-01 |
| IAM-BR11 | Kode menu unik (`DUPLICATE`); referensi permission atau induk harus ada; siklus hierarki ditolak (`VALIDATION_ERROR`); menu induk yang masih punya submenu aktif tidak dapat dinonaktifkan (`ENTITY_IN_USE`) | AC-14 |
| IAM-BR12 | Penugasan gudang disimpan di `user_warehouses` dan hanya dapat diubah pengguna ber-`user:manage` | 3.2 |
| IAM-BR13 | Aksi bertanda (g) pada matriks permission hanya boleh dilakukan pada gudang yang ditugaskan; pelanggaran ditolak 403 `WAREHOUSE_NOT_ASSIGNED` | 3.2 |
| IAM-BR14 | Gudang yang diperiksa untuk tiap aksi ditentukan modul dokumen pemilik aksi itu (lihat aturan scoping di RCV dan TRF), bukan oleh IAM | 3.2 |
| IAM-BR15 | Pada pembacaan, Warehouse Staff hanya melihat dokumen dan stok gudang yang ditugaskan; Transfer terlihat bila ditugaskan di gudang asal atau tujuan. Super Admin, Warehouse Manager, Purchasing Staff (stok dan dokumen), dan Auditor tidak dibatasi penugasan | 3.2 |
| IAM-BR16 | `roles`, `role_permissions`, `users`, `user_warehouses`, dan `refresh_tokens` milik satu tenant; username unik per tenant (GBR-18). `permissions` dan `menus` bersifat global karena kodenya milik modul, bukan milik tenant | Baru v3.1 |
| IAM-BR17 | Login menerima slug tenant, username, dan kata sandi. Slug tidak dikenal, tenant nonaktif, atau kredensial salah dijawab sama (401 `AUTH_INVALID_CREDENTIALS`) agar keberadaan tenant tidak bocor; tenant ditangguhkan dijawab 403 `TENANT_SUSPENDED` hanya setelah kredensial terbukti benar | Baru v3.1 |
| IAM-BR18 | Access token memuat `tenant_id` (menambah IAM-BR01). Pada setiap request IAM memastikan tenant token sama dengan tenant pengguna di database dan berstatus aktif (IAM-BR02, GBR-17) | Baru v3.1 |
| IAM-BR19 | Lima peran bawaan disalin ke setiap tenant baru lewat `provision_tenant_access`. Pengelolaan peran dan permission (IAM-F06) hanya berlaku pada tenant sendiri; tenant tidak dapat menambah kode permission, dan peran bawaan tidak dapat dihapus | Baru v3.1 |
| IAM-BR20 | Platform Admin tidak disimpan di `users` dan tidak memiliki peran tenant; tabel dan alur loginnya mengikuti OQ-12 (Perlu Ditinjau) | Baru v3.1 |

**Permission dan API**

- Permission milik IAM: `user:manage`.
- Auth: `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/change-password`.
- Pengguna: `GET/POST /users`, `GET/PATCH /users/{id}`, `GET/PUT /users/{id}/warehouses`, `GET /users/roles`, `GET /users/permissions`, `PUT /users/roles/{id}/permissions`.
- Menu: `GET /menus/my-menu`, `GET/POST /menus`, `GET/PATCH /menus/{id}`.
- Daftar endpoint diambil dari PRD v2.0 Lampiran B dan `PRD_FRONTEND.md` bagian 17; bila kode berbeda, kode yang berlaku.

**Kriteria penerimaan**

| AC | Skenario ringkas |
| --- | --- |
| AC-05 | Warehouse Staff yang menerbitkan PO atau menyetujui akhir Opname ditolak 403. Setiap perubahan sah menulis satu baris audit log (sisi audit diverifikasi bersama AUD) |
| AC-11 | Refresh token R1 dipakai: terbit R2 dan R1 revoked. R1 dipakai lagi: 401, semua token aktif pengguna dicabut, tercatat di audit log. Setelah logout token tidak dapat dipakai |
| AC-12 | Warehouse Staff yang hanya ditugaskan di Gudang A memposting GR untuk PO bergudang tujuan B: ditolak 403 `WAREHOUSE_NOT_ASSIGNED` |
| AC-14 | Pohon menu tersaring sesuai IAM-BR09; operasi admin menu tanpa `user:manage` ditolak 403 `PERMISSION_DENIED`; menu duplikat, referensi tak ada, siklus, dan penonaktifan induk beranak ditolak sesuai IAM-BR11 |

**Titik perluasan**

- Permission, role, dan menu baru ditambahkan lewat migrasi seed baru tanpa mengubah modul lain.
- Mengganti penyimpanan refresh token (misalnya ke cookie HttpOnly) adalah perubahan kontrak login, refresh, dan logout; tergolong perubahan besar (MAJOR).

### AUD — Audit

AUD menyimpan jejak siapa mengubah apa dan kapan, dan jejak itu tidak pernah dapat diubah.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-09, bagian 6.4 (sisi audit log) |
| Peta kode | `api/routes/audit_logs.py`, `services/audit_service.py`, `repositories/audit_repo.py`, migrasi 006 (bagian `audit_logs`) dan 007 |
| Bergantung pada | Lintas-lapisan: `authorize` milik IAM |
| Dipakai oleh | Semua modul yang mengubah data, lewat kontrak `record` |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| AUD-F01 | Pencatatan otomatis perubahan data dan aktivitas autentikasi penting | P0 | FR-09 |
| AUD-F02 | Pembacaan dan penyaringan audit log | P0 | FR-09 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| AUD-BR01 | Wajib tercatat otomatis: perubahan data master, perubahan status transaksi, perubahan hak akses dan penugasan gudang, login berhasil dan gagal, logout, serta pemakaian ulang refresh token yang sudah dicabut | FR-09 |
| AUD-BR02 | Setiap entri memuat `user_id` (kosong untuk login gagal yang tidak dikenali), `action`, `entity_type`, `entity_id`, `old_values` dan `new_values` (JSONB), alamat IP, dan waktu | FR-09 |
| AUD-BR03 | Entri ditulis dalam transaksi yang sama dengan perubahan yang dicatatnya (GBR-03), sehingga perubahan yang dibatalkan tidak meninggalkan entri | 7.1, AC-07 |
| AUD-BR04 | `audit_logs` mengikuti GBR-02; tidak ada endpoint ubah atau hapus, termasuk untuk Super Admin | 6.4 |

**Permission dan API**

- Permission milik AUD: `audit:read` (Super Admin dan Auditor).
- `GET /audit-logs` dengan filter `user_id`, `action`, `entity_type`, `entity_id`, `date_from`, `date_to`, pagination, dan pengurutan. Tidak ada pencarian teks bebas pada endpoint ini.

**Kriteria penerimaan**

- AUD tidak memiliki AC sendiri. Ia diverifikasi lewat AC-05 (IAM, sisi audit), AC-07 (RCV, atomisitas), dan AC-08 (INV, imutabilitas).

**Titik perluasan**

- Modul baru mencatat peristiwanya dengan memanggil `record`; AUD tidak perlu diubah. Filter baru ditambahkan di AUD saja.

### TNT — Tenant

TNT memiliki tenant, yaitu perusahaan pelanggan yang memakai JejakStok, beserta siklus hidup, paket, dan batas pemakaiannya. Semua data bisnis milik tepat satu tenant dan tidak terlihat oleh tenant lain (GBR-16 sampai GBR-18).

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP (keputusan 2026-11-02) |
| Asal v2.0 | Baru di v3.1; PRD v2.0 mengasumsikan satu organisasi |
| Peta kode | `routes/tenant_routes.py`, `routes/platform_routes.py`, `services/tenant_service.py`, `repositories/tenant_repo.py`, `schemas/tenant.py`, migrasi 010 (nama berkas Perlu Ditinjau terhadap `FOLDER_STRUCTURE.MD`, OQ-10) |
| Bergantung pada | Tulis: `provision_tenant_access` (IAM), `seed_tenant_settings` (CFG). Lintas-lapisan: `record` (AUD) |
| Dipakai oleh | IAM (`tenant_status`, `check_quota`), MST dan WHS (`check_quota`) |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | --- | --- |
| TNT-F01 | Pendaftaran tenant: membuat tenant, Super Admin pertama, peran bawaan, dan pengaturan bawaan dalam satu transaksi | P0 | Baru v3.1 |
| TNT-F02 | Profil tenant: nama, slug, dan data kontak | P0 | Baru v3.1 |
| TNT-F03 | Siklus hidup tenant: aktif, ditangguhkan, nonaktif | P0 | Baru v3.1 |
| TNT-F04 | Paket dan batas pemakaian: gudang, pengguna aktif, barang aktif | P1 | Baru v3.1 |
| TNT-F05 | Operasi platform: daftar, lihat, tangguhkan, aktifkan ulang, nonaktifkan, dan ubah paket tenant oleh Platform Admin | P0 | Baru v3.1 |
| TNT-F06 | Ekspor data tenant saat berhenti berlangganan | P2 | Baru v3.1 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| TNT-BR01 | Tenant dikenali lewat `slug` yang unik secara global (huruf kecil, angka, tanda hubung) dan tidak dapat diubah setelah dibuat; slug dipakai pada login (IAM-BR17). Slug yang sudah dipakai ditolak 409 `DUPLICATE` | Baru v3.1 |
| TNT-BR02 | Pendaftaran tenant adalah satu transaksi: baris tenant, `provision_tenant_access`, `seed_tenant_settings`, dan audit log. Gagal di langkah mana pun berarti tidak ada tenant, pengguna, atau pengaturan yang tersisa (GBR-03) | Baru v3.1 |
| TNT-BR03 | Status tenant: `ACTIVE`, `SUSPENDED`, `DEACTIVATED`. Tenant tidak dihapus (GBR-01); `DEACTIVATED` bersifat final dan datanya tetap tersimpan sesuai kebijakan retensi (OQ-15) | Baru v3.1 |
| TNT-BR04 | Tenant `SUSPENDED` atau `DEACTIVATED` ditolak 403 `TENANT_SUSPENDED` pada login, refresh, dan setiap request, termasuk dengan token yang sudah terbit (IAM-BR18). Data tenant tidak berubah | Baru v3.1 |
| TNT-BR05 | Batas paket (gudang, pengguna aktif, barang aktif) diperiksa saat membuat entitas itu; melebihi batas ditolak 409 `TENANT_LIMIT_EXCEEDED`. Pemeriksaan dan pembuatan satu transaksi dengan baris tenant dikunci `FOR UPDATE`, kunci yang tidak bersilang dengan kunci stok GBR-07. Menurunkan paket tidak memotong data yang sudah ada, hanya menahan penambahan | Baru v3.1 |
| TNT-BR06 | Operasi platform hanya untuk Platform Admin lewat jalur `/platform/...` dengan permission platform. Platform Admin tidak membaca stok atau dokumen tenant; akses dukungan ke data tenant ditetapkan di OQ-17 | Baru v3.1 |
| TNT-BR07 | Setiap operasi platform dicatat di audit log dengan tenant sasaran, pelaku, dan nilai lama serta baru | Baru v3.1 |
| TNT-BR08 | Tidak ada endpoint yang menerima `tenant_id` dari klien; tenant selalu berasal dari token (GBR-17) | Baru v3.1 |

**Status dan transisi**

| Dari | Ke | Aksi | Pelaku |
| --- | --- | --- | --- |
| `ACTIVE` | `SUSPENDED` | suspend | Platform Admin |
| `SUSPENDED` | `ACTIVE` | reactivate | Platform Admin |
| `ACTIVE`, `SUSPENDED` | `DEACTIVATED` | deactivate (final) | Platform Admin |

**Permission dan API**

- Permission tenant: `tenant:read`, `tenant:update`. Permission platform: `platform:tenant_read`, `platform:tenant_manage`.
- Sisi tenant: `GET /tenant` (profil dan pemakaian kuota), `PATCH /tenant`.
- Sisi platform: `POST /platform/tenants`, `GET /platform/tenants`, `GET /platform/tenants/{id}`, `POST /platform/tenants/{id}/suspend`, `POST /platform/tenants/{id}/reactivate`, `POST /platform/tenants/{id}/deactivate`, `PUT /platform/tenants/{id}/plan`.
- Daftar endpoint adalah usulan dan belum diverifikasi terhadap kode (AS-02).

**Kriteria penerimaan**

| AC | Skenario | Hasil yang diharapkan |
| --- | --- | --- |
| AC-15 | Pengguna tenant A meminta barang, dokumen, saldo, ledger, atau audit milik tenant B dengan ID yang valid | 404 `NOT_FOUND`; daftar tidak memuat baris tenant B; query tanpa konteks tenant gagal |
| AC-16 | Platform Admin menangguhkan tenant yang punya sesi aktif | Login, refresh, dan request dengan token lama ditolak 403 `TENANT_SUSPENDED`; setelah diaktifkan ulang kembali berfungsi |
| AC-17 | Pendaftaran tenant gagal pada langkah penyalinan peran atau pengaturan | Tidak ada tenant, pengguna, peran, atau pengaturan yang tersisa |
| AC-18 | Tenant dengan batas satu gudang membuat gudang kedua | 409 `TENANT_LIMIT_EXCEEDED`; dua permintaan bersamaan hanya satu yang berhasil |
| AC-19 | Dua tenant memakai SKU, kode gudang, dan awalan nomor dokumen yang sama | Diizinkan; dalam satu tenant ditolak 409 `DUPLICATE`; urutan nomor dokumen tiap tenant berjalan terpisah |

**Titik perluasan**

- Paket baru cukup baris di `plans`; batas baru menambah kolom paket dan jenis pada `check_quota`.
- Pendaftaran mandiri, penagihan, SSO per tenant, dan domain khusus menjadi modul atau fitur baru tanpa mengubah kontrak TNT (OOS-11 sampai OOS-14).

### CFG — Konfigurasi

CFG memiliki pengaturan bertingkat: nilai bawaan dari registri kunci, ditimpa tingkat tenant, lalu tingkat gudang. Perbedaan perilaku antar-tenant atau antar-gudang diatur di sini dan bukan lewat percabangan kode (BND-08).

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP (keputusan 2026-11-02) |
| Asal v2.0 | Baru di v3.1. Nilai yang sudah dimiliki modul lain, seperti pengaturan stok negatif di WHS, tetap milik modul itu (BND-01) |
| Peta kode | `routes/settings_routes.py`, `services/settings_service.py`, `repositories/settings_repo.py`, `schemas/settings.py`, `core/settings_registry.py`, migrasi 010 (Perlu Ditinjau, OQ-10) |
| Bergantung pada | Lintas-lapisan: `authorize` (IAM), `record` (AUD), `current_tenant` (PLT). Baca: `warehouses` (WHS) untuk tingkat gudang |
| Dipakai oleh | Semua modul (`get_setting`), TNT (`seed_tenant_settings`) |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | --- | --- |
| CFG-F01 | Registri kunci pengaturan: nama, jenis nilai, bawaan, tingkat yang boleh menimpa | P0 | Baru v3.1 |
| CFG-F02 | Pengaturan tingkat tenant | P0 | Baru v3.1 |
| CFG-F03 | Pengaturan tingkat gudang | P1 | Baru v3.1 |
| CFG-F04 | Pembacaan nilai efektif lewat `get_setting` | P0 | Baru v3.1 |
| CFG-F05 | Label dan lokal tampilan: bahasa, zona waktu, mata uang, istilah | P1 | Baru v3.1 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| CFG-BR01 | Nilai efektif ditentukan berurutan: gudang, tenant, bawaan registri. Kunci yang tidak terdaftar ditolak 422 `SETTING_INVALID` | Baru v3.1 |
| CFG-BR02 | Kunci hanya dapat diubah pada tingkat yang diizinkan registri; kunci `display.*` dan `label.*` hanya pada tingkat tenant | Baru v3.1 |
| CFG-BR03 | Nilai divalidasi menurut jenis dan rentang kunci; yang tidak valid ditolak 422 `SETTING_INVALID` | Baru v3.1 |
| CFG-BR04 | Tingkat tenant hanya dapat diubah Super Admin; tingkat gudang dapat diubah Warehouse Manager pada gudang yang ditugaskan (`WAREHOUSE_NOT_ASSIGNED` bila tidak) | Baru v3.1 |
| CFG-BR05 | Setiap perubahan dicatat di audit log dengan nilai lama dan baru. Tidak ada hapus permanen (GBR-01); reset menonaktifkan penimpaan sehingga nilai tingkat di atasnya berlaku kembali | Baru v3.1 |
| CFG-BR06 | Perubahan hanya berlaku untuk dokumen dan aksi baru. Bila sebuah kunci memengaruhi hasil dokumen, modul pemilik dokumen menyalin nilainya ke dokumen saat dibuat sehingga dokumen lama dan ledger tidak berubah (GBR-02) | Baru v3.1 |
| CFG-BR07 | `get_setting` hanya membaca dan tidak membuka transaksi tulis; hasilnya boleh disimpan sementara selama satu request | Baru v3.1 |

**Registri kunci pengaturan (awal)**

| Kunci | Jenis | Bawaan | Tingkat |
| --- | --- | --- | --- |
| `display.locale` | Kode bahasa BCP 47 | `id-ID` | Tenant |
| `display.timezone` | Nama zona IANA; hanya untuk tampilan, penyimpanan tetap UTC (GBR-14) | `Asia/Jakarta` | Tenant |
| `display.currency` | Kode ISO 4217 | `IDR` | Tenant |
| `label.warehouse` | Teks; istilah pengganti "Gudang", misalnya "Toko" atau "Site" | `Gudang` | Tenant |

Nilai bawaan di atas adalah usulan (Perlu Ditinjau). Modul lain mendaftarkan kuncinya sendiri lewat prosedur perubahan.

**Permission dan API**

- Permission: `settings:read`, `settings:manage`. Kunci `display.*` dan `label.*` juga dibaca semua pengguna terautentikasi lewat endpoint publik tanpa permission.
- Usulan endpoint (AS-02): `GET /settings`, `GET /settings/effective`, `GET /settings/public`, `PUT /settings/{key}`, `POST /settings/{key}/reset`.

**Kriteria penerimaan**

| AC | Skenario | Hasil yang diharapkan |
| --- | --- | --- |
| AC-20 | Kunci diatur pada tingkat tenant dan gudang, lalu penimpaan gudang di-reset | Gudang memakai nilai gudang; setelah reset memakai nilai tenant; tenant tanpa penimpaan memakai bawaan registri |
| AC-21 | Mengubah kunci tak terdaftar, nilai di luar rentang, atau tingkat tenant oleh Warehouse Manager | 422 `SETTING_INVALID` untuk dua kasus pertama; 403 `PERMISSION_DENIED` untuk kasus ketiga |

**Titik perluasan**

- Modul baru menambah kunci ke registri, misalnya ambang persetujuan Opname atau strategi pengeluaran FIFO dan FEFO pada ISS, tanpa menyentuh modul lain.
- Tingkat baru, misalnya per kategori barang, menambah nilai tingkat tanpa mengubah urutan baca yang ada.
- Kunci `feature.*` yang dibatasi paket memungkinkan fitur dinyalakan per tenant (kontrak dengan TNT ditetapkan saat dibutuhkan).

### MST — Master Data

MST memiliki katalog barang, satuan, kategori, dan pemasok yang dirujuk semua dokumen transaksi.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-02, bagian 6.8 (sisi barang dan pemasok), Lampiran A |
| Peta kode | `api/routes/master.py`, `services/master_service.py`, `repositories/master_repo.py`, schema `master`, migrasi 002 (bagian kategori, UoM, barang, pemasok) |
| Bergantung pada | Baca: `open_references` milik INV, PUR, RCV, TRF, OPN, serta check\_quota milik TNT. Lintas-lapisan: current\_tenant milik PLT, `authorize`, `record` |
| Dipakai oleh | INV, PUR, RCV, TRF, OPN |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| MST-F01 | Kategori barang | P0 | FR-02 |
| MST-F02 | Satuan ukur (UoM) dengan atribut `allow_decimal` | P0 | FR-02 |
| MST-F03 | Barang dengan SKU unik | P0 | FR-02 |
| MST-F04 | Pemasok | P0 | FR-02 |
| MST-F05 | Penonaktifan terkontrol (tanpa hapus permanen) | P0 | FR-02, 6.8 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| MST-BR01 | Setiap barang memiliki tepat satu UoM dasar; seluruh PO, GR, Transfer, dan Opname memakai UoM itu | FR-02, OOS-07 |
| MST-BR02 | UoM memiliki `allow_decimal` (bawaan `FALSE`). Maknanya pada kuantitas diatur GBR-05 | FR-02 |
| MST-BR03 | SKU unik (`DUPLICATE`) dan tidak dapat diubah setelah barang dipakai pada transaksi apa pun | FR-02, 6.8 |
| MST-BR04 | Nama kategori, kode UoM, dan kode pemasok masing-masing unik | Lampiran A |
| MST-BR05 | Penonaktifan barang mengikuti GBR-13. Pemasok yang masih punya PO non-final tidak dapat dinonaktifkan | 6.8 |

**Permission dan API**

- Permission milik MST: `master:manage` (Super Admin, Purchasing Staff) dan `master:read` (semua peran).
- `GET/POST /categories`, `/uoms`, `/suppliers`, `/items` dan `GET/PATCH` pada `/{id}`. Daftar mendukung `limit`, `offset`, `is_active`, `search`, `sort_by`, `sort_dir`.

**Kriteria penerimaan**

- v2.0 tidak memiliki AC untuk master data; lihat OQ-03.

**Titik perluasan**

- Atribut barang tambahan yang tidak memengaruhi kunci saldo cukup menambah kolom di MST. Atribut yang mengubah identitas stok, seperti lot atau nomor seri (OOS-01, OOS-02), mengubah kunci saldo INV dan tergolong perubahan besar.

### WHS — Gudang dan Lokasi

WHS memiliki struktur fisik tempat stok berada: gudang dan lokasi penyimpanan di dalamnya.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-02 (gudang, lokasi), bagian 6.3 (sisi lokasi), 6.8, Lampiran A |
| Peta kode | `api/routes/warehouses.py`, `services/warehouse_service.py`, `repositories/warehouse_repo.py`, schema `warehouse`, migrasi 002 (bagian gudang dan lokasi) |
| Bergantung pada | Baca: `open_references` milik INV, PUR, RCV, TRF, OPN, serta check\_quota milik TNT. Lintas-lapisan: current\_tenant milik PLT, `authorize`, `record` |
| Dipakai oleh | IAM (penugasan gudang), CFG (tingkat gudang), INV, PUR, RCV, TRF, OPN |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| WHS-F01 | Gudang dengan pengaturan `allow_negative_stock` | P0 | FR-02 |
| WHS-F02 | Lokasi penyimpanan (bin atau rak) di dalam gudang | P0 | FR-02 |
| WHS-F03 | Validasi lokasi lewat kontrak baca `validate_location` | P0 | 6.3 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| WHS-BR01 | `allow_negative_stock` bernilai `FALSE` secara bawaan, hanya Super Admin yang dapat mengubahnya, dan perubahannya tercatat di audit log. Dampaknya pada stok diatur INV-BR03 | FR-02 |
| WHS-BR02 | Kode gudang unik; kode lokasi unik di dalam satu gudang | FR-02, Lampiran A |
| WHS-BR03 | Lokasi yang dipilih pada transaksi harus aktif dan milik gudang yang dirujuk (`INVALID_LOCATION`). Kepemilikan juga dijaga composite foreign key `(location_id, warehouse_id)` di database | 6.3 |
| WHS-BR04 | Penonaktifan gudang atau lokasi mengikuti GBR-13 | 6.8 |

**Permission dan API**

- Permission milik WHS: `warehouse:manage` (Super Admin) dan `location:manage` (Super Admin, Warehouse Manager pada gudang yang ditugaskan). Membaca memakai `master:read`.
- `GET/POST /warehouses`, `GET/PATCH /warehouses/{id}`, `GET/POST /warehouses/{id}/locations`, `GET/POST /locations`, `GET/PATCH /locations/{id}`.

**Kriteria penerimaan**

- v2.0 tidak memiliki AC untuk gudang dan lokasi; lihat OQ-03.

**Titik perluasan**

- Atribut gudang atau lokasi baru cukup ditambahkan di WHS. Selama kunci saldo tetap gudang, lokasi, dan barang, INV tidak terpengaruh.

### INV — Inventory

INV adalah satu-satunya pemilik saldo stok dan ledger; setiap perubahan stok masuk lewat satu pintu, `apply_movement`.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-03, FR-08, bagian 5.3, 6.1, 6.4 (sisi ledger), 6.5; AC-08 |
| Peta kode | `api/routes/stock.py`, `services/inventory_service.py`, `services/stock_service.py`, `repositories/inventory_repo.py`, schema `stock`, migrasi 003 dan 007 |
| Bergantung pada | Baca: MST (barang), `validate_location` (WHS), `is_location_frozen` (OPN), `in_transit` (TRF). Lintas-lapisan: `authorize`, `record` |
| Dipakai oleh | Tulis: RCV, TRF, OPN. Baca: MST, WHS, RPT |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| INV-F01 | Saldo stok per gudang, lokasi, dan barang | P0 | FR-03 |
| INV-F02 | Tampilan stok per lokasi, per gudang, agregat lintas gudang, ringkasan barang, dengan kolom stok dalam perjalanan | P0 | FR-03 |
| INV-F03 | Ledger pergerakan stok append-only beserta pembacaannya | P0 | FR-08 |
| INV-F04 | `apply_movement` sebagai satu-satunya pintu perubahan stok | P0 | FR-08 |
| INV-F05 | Pencegahan stok negatif per gudang | P0 | 6.1 |
| INV-F06 | Penolakan pergerakan pada lokasi yang dibekukan | P0 | 6.6 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| INV-BR01 | Baris saldo dibuat otomatis pada pergerakan pertama dengan nilai awal 0, lewat upsert `INSERT ... ON CONFLICT DO NOTHING` sebelum dikunci. Kombinasi `(warehouse_id, location_id, item_id)` unik | FR-03, 6.5 |
| INV-BR02 | Setiap perubahan kuantitas menulis satu baris ledger berisi tipe, gudang, lokasi, barang, `qty_before`, `qty_change` (positif untuk penambahan, negatif untuk pengurangan), `qty_after`, `reference_type`, `reference_id`, pelaksana, dan waktu. Invarian: `qty_after = qty_before + qty_change`, dan `qty_after` baris terakhir sama dengan `qty_on_hand` | FR-08 |
| INV-BR03 | Bila `qty_change` negatif, gudang ber-`allow_negative_stock = FALSE`, dan `qty_before + qty_change` kurang dari 0, seluruh transaksi ditolak 409 `INSUFFICIENT_STOCK` berikut barang, stok tersedia, dan kuantitas diminta. Pemeriksaan dilakukan di aplikasi setelah baris saldo dikunci; tabel tidak diberi `CHECK (qty_on_hand >= 0)` karena aturannya per gudang. Bila `TRUE`, saldo boleh negatif dan `qty_after` mencatat nilai negatif itu | 6.1 |
| INV-BR04 | Pergerakan selain `ADJUSTMENT_*` ditolak 409 `LOCATION_FROZEN` bila lokasi sedang dibekukan Opname (OPN-BR05). Pemeriksaan dilakukan setelah kunci lokasi didapat, agar tidak lolos di antara dua transaksi bersamaan | 6.6 |
| INV-BR05 | Urutan langkah `apply_movement`, di dalam transaksi pemanggil: (1) kunci lokasi `FOR SHARE` dan periksa pembekuan, (2) pastikan baris saldo ada, (3) kunci baris saldo `FOR UPDATE`, (4) validasi stok negatif, (5) perbarui saldo, (6) tulis ledger. Pemanggil mengurutkan baris dokumennya sesuai GBR-07 | 6.5 |
| INV-BR06 | Stok dalam perjalanan adalah kuantitas Transfer berstatus `SHIPPED` yang belum `RECEIVED`; datanya disediakan TRF, INV hanya menampilkannya | FR-03 |

**Registri tipe pergerakan**

| Tipe | Pemicu | Arah | `reference_type` | Modul pemicu |
| --- | --- | :-: | --- | --- |
| `IN_PURCHASE` | GR menjadi `POSTED` | + | `GOODS_RECEIPT` | RCV |
| `OUT_TRANSFER` | Transfer menjadi `SHIPPED` | − | `STOCK_TRANSFER` | TRF |
| `IN_TRANSFER` | Transfer menjadi `RECEIVED` | + | `STOCK_TRANSFER` | TRF |
| `ADJUSTMENT_PLUS` | Opname `COMPLETED`, selisih positif | + | `STOCK_OPNAME` | OPN |
| `ADJUSTMENT_MINUS` | Opname `COMPLETED`, selisih negatif | − | `STOCK_OPNAME` | OPN |

**Permission dan API**

- Permission milik INV: `stock:read` dan `ledger:read`, keduanya dibatasi gudang yang ditugaskan untuk Warehouse Staff.
- `GET /stock/balances` (alias `/stock/by-location`), `GET /stock/by-warehouse`, `GET /stock/summary`, `GET /stock/movements` (alias `/stock/ledger`). Alias mengembalikan response yang sama.
- Filter saldo: `warehouse_id`, `location_id`, `item_id`, `category_id`, `search`. Filter ledger menambah `movement_type`, `reference_type`, `reference_id`, `date_from`, `date_to`.

**Kriteria penerimaan**

| AC | Skenario ringkas |
| --- | --- |
| AC-08 | `UPDATE` atau `DELETE` pada `stock_movements` dan `audit_logs`, termasuk lewat koneksi SQL langsung memakai role `wms_app`, ditolak database dan data tidak berubah |

Penegakan INV-BR03 dan INV-BR04 diverifikasi lewat AC-02 dan AC-06 (TRF) serta AC-10 (OPN).

**Titik perluasan**

- Tipe pergerakan baru, misalnya untuk Goods Issue, cukup menambah baris pada registri dan migrasi `CHECK` baru; tanda tangan `apply_movement` tidak berubah.
- Mengubah kunci saldo, misalnya menambah lot atau nomor seri, adalah perubahan besar yang menyentuh INV, RCV, TRF, dan OPN sekaligus.

### PUR — Purchase Order

PUR mengelola pesanan ke pemasok dan melacak berapa banyak dari tiap baris yang sudah diterima.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-04, bagian 5.1 (PO), 6.2 (sisi PO), 6.3 (PO), 6.8 (pemasok) |
| Peta kode | `api/routes/purchase_orders.py`, `services/po_service.py`, `repositories/po_repo.py`, schema `purchase_order`, migrasi 004 (bagian `purchase_orders` dan `po_lines`) |
| Bergantung pada | Baca: MST (pemasok, barang), WHS (gudang tujuan), `gr_status_summary` (RCV). Lintas-lapisan: `authorize`, `record`. PLT: `next_number` |
| Dipakai oleh | Tulis: RCV lewat `apply_receipt`. Baca: RPT |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| PUR-F01 | PO dengan header dan baris barang | P0 | FR-04 |
| PUR-F02 | Siklus status: terbit, batal, tutup | P0 | 5.1 |
| PUR-F03 | Pelacakan pemenuhan: `qty_received` per baris dan status otomatis | P0 | FR-04 |
| PUR-F04 | Kontrak tulis `apply_receipt` untuk RCV | P0 | FR-05 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| PUR-BR01 | PO memiliki header (pemasok, satu gudang tujuan, tanggal pesan, catatan) dan satu baris atau lebih, masing-masing dengan `qty_ordered` lebih dari 0 | FR-04 |
| PUR-BR02 | Satu barang hanya boleh muncul satu kali per PO | FR-04, 6.3 |
| PUR-BR03 | Pada setiap baris berlaku `0 <= qty_received <= qty_ordered` | FR-04 |
| PUR-BR04 | Header dan baris hanya dapat diubah saat `DRAFT` | FR-04 |
| PUR-BR05 | PO baru mensyaratkan pemasok dan gudang tujuan yang aktif (GBR-11) | 5.1 |
| PUR-BR06 | Penerbitan mensyaratkan minimal satu baris, seluruh `qty_ordered` lebih dari 0, dan barang aktif. Penerbitan oleh pengguna berwenang dianggap persetujuan (OOS-09) | 5.1 |
| PUR-BR07 | PO `ISSUED` hanya dapat dibatalkan bila belum ada GR `POSTED` dan tidak ada GR `DRAFT` | 5.1 |
| PUR-BR08 | PO hanya dapat ditutup bila tidak ada GR `DRAFT`, dengan alasan penutupan wajib. Sisa pesanan yang belum dikirim dianggap tidak dilanjutkan | 5.1 |
| PUR-BR09 | Status `PARTIALLY_RECEIVED` dan `RECEIVED` ditentukan otomatis oleh `apply_receipt`: sebagian bila total `qty_received` lebih dari 0 dan masih ada baris belum penuh, penuh bila seluruh baris `qty_received = qty_ordered`. GR berikutnya yang masih menyisakan kuantitas tidak mengubah status | 5.1 |

**Status dan transisi**

| Transisi | Pemicu | Syarat | Efek |
| --- | --- | --- | --- |
| baru → `DRAFT` | `po:create` | Pemasok dan gudang tujuan aktif | PO dapat diubah; belum dapat dipakai untuk penerimaan |
| `DRAFT` → `ISSUED` | `po:issue` | PUR-BR06 | Baris dikunci dari perubahan; siap menerima GR |
| `DRAFT` → `CANCELLED` | `po:create` | Tidak ada | PO dibatalkan |
| `ISSUED` → `CANCELLED` | `po:cancel` | PUR-BR07 | PO dibatalkan |
| `ISSUED` → `PARTIALLY_RECEIVED` | Sistem, saat GR `POSTED` | PUR-BR09 | Tidak ada |
| `ISSUED` atau `PARTIALLY_RECEIVED` → `RECEIVED` | Sistem, saat GR `POSTED` | PUR-BR09 | Status final |
| `ISSUED` atau `PARTIALLY_RECEIVED` → `CLOSED` | `po:close` | PUR-BR08 | Status final |

**Permission dan API**

- Permission milik PUR: `po:create`, `po:issue`, `po:cancel`, `po:close`, `po:read`. Membatalkan PO `DRAFT` memakai `po:create`; membatalkan PO `ISSUED` memakai `po:cancel`.
- `GET/POST /purchase-orders`, `GET/PATCH /purchase-orders/{id}`, `POST /purchase-orders/{id}/issue`, `/cancel`, `/close`.
- Pembuatan: `{supplier_id, warehouse_id, order_date, notes, lines: [{item_id, qty_ordered, notes}]}`. Penutupan: `{closed_reason}`. Filter daftar: `warehouse_id`, `supplier_id`, `status`, `date_from`, `date_to`, `search`.

**Kriteria penerimaan**

- PUR tidak memiliki AC sendiri. Sisi PO dari AC-01 (status berubah menjadi `PARTIALLY_RECEIVED` lalu `RECEIVED`) diverifikasi lewat skenario RCV.

**Titik perluasan**

- Persetujuan berjenjang (OOS-09) menambah status dan permission di PUR dan IAM tanpa menyentuh RCV, selama kontrak `apply_receipt` tetap.

### RCV — Goods Receipt

RCV mencatat barang yang benar-benar datang terhadap sebuah PO dan menambah stok secara atomik saat dokumen diposting.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-05, bagian 5.1 (GR), 5.2 butir 1, 6.2; AC-01, AC-07, AC-13 |
| Peta kode | `api/routes/goods_receipts.py`, `services/gr_service.py`, `repositories/gr_repo.py`, schema `goods_receipt`, migrasi 004 (bagian `goods_receipts` dan `gr_lines`) |
| Bergantung pada | Tulis: `apply_movement` (INV), `apply_receipt` (PUR), `next_number` (PLT). Baca: `validate_location` (WHS). Lintas-lapisan: `authorize`, `record` |
| Dipakai oleh | Baca: PUR (`gr_status_summary`), RPT |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| RCV-F01 | Membuat GR dari PO yang dapat menerima barang; beberapa GR per PO | P0 | FR-05 |
| RCV-F02 | Posting GR atomik: stok, PO, ledger, audit | P0 | FR-05 |
| RCV-F03 | Pembatalan GR `DRAFT` | P0 | 5.1 |
| RCV-F04 | Pencegahan penerimaan melebihi pesanan | P0 | 6.2 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| RCV-BR01 | GR hanya dapat dibuat dari PO berstatus `ISSUED` atau `PARTIALLY_RECEIVED`; satu PO boleh memiliki beberapa GR | FR-05 |
| RCV-BR02 | Gudang GR sama dengan gudang tujuan PO; lokasi penyimpanan ditentukan pada setiap baris GR | FR-05 |
| RCV-BR03 | Setiap baris GR merujuk satu baris PO (`po_line_id`) dengan `qty_received` lebih dari 0; barang di luar PO tidak dapat diterima | FR-05 |
| RCV-BR04 | `qty_received` pada GR ini ditambah `qty_received` baris PO tidak boleh melebihi `qty_ordered`; `qty_received` baris PO hanya menghitung GR `POSTED`. Pelanggaran ditolak 409 `OVER_RECEIPT` | 6.2 |
| RCV-BR05 | Validasi kuantitas dijalankan saat GR dibuat atau diubah sebagai peringatan awal, lalu dihitung ulang saat posting setelah baris PO dikunci (`SELECT ... FOR UPDATE`); hasil saat posting yang mengikat. GR `DRAFT` tidak mencadangkan kuantitas PO | FR-05, 6.2 |
| RCV-BR06 | Lokasi pada baris GR harus aktif, milik gudang, dan tidak dibekukan Opname (INV-BR04); status PO dicek ulang saat posting | 5.1 |
| RCV-BR07 | Posting berjalan dalam satu transaksi dengan urutan: kunci header GR (status harus `DRAFT`), periksa penugasan gudang, kunci PO dan barisnya, hitung ulang over-receipt, `apply_movement` bertipe `IN_PURCHASE` untuk setiap baris secara berurutan, `apply_receipt`, tandai GR `POSTED`, `record` untuk GR dan PO | FR-05, GBR-03 |
| RCV-BR08 | GR `POSTED` tidak dapat dibalik; koreksi atas kesalahan penerimaan dilakukan lewat Stock Opname (OOS-06) | 5.1 |
| RCV-BR09 | Gudang tujuan GR harus termasuk gudang yang ditugaskan kepada pengguna (IAM-BR13); pelanggaran ditolak 403 `WAREHOUSE_NOT_ASSIGNED` | 3.2 |

**Status dan transisi**

| Transisi | Pemicu | Syarat | Efek |
| --- | --- | --- | --- |
| baru → `DRAFT` | `gr:manage` | RCV-BR01, RCV-BR09 | Dokumen disiapkan; belum mengubah stok |
| `DRAFT` → `POSTED` | `gr:manage` | RCV-BR04, RCV-BR06 | Menambah saldo, menulis ledger `IN_PURCHASE`, memperbarui `qty_received` dan status PO. Status final |
| `DRAFT` → `CANCELLED` | `gr:manage` | Tidak ada | Dokumen dibatalkan |

**Permission dan API**

- Permission milik RCV: `gr:manage` (Super Admin, Warehouse Staff pada gudang yang ditugaskan) dan `gr:read`.
- `GET/POST /goods-receipts`, `GET/PATCH /goods-receipts/{id}`, `POST /goods-receipts/{id}/post`, `/cancel`.
- Pembuatan: `{po_id, received_date, notes, lines: [{po_line_id, location_id, qty_received, notes}]}`. Filter daftar: `warehouse_id`, `po_id`, `status`, `date_from`, `date_to`, `search`.

**Kriteria penerimaan**

| AC | Skenario ringkas |
| --- | --- |
| AC-01 | PO `ISSUED` memesan 50 unit Barang X. GR pertama 20 unit diposting: PO menjadi `PARTIALLY_RECEIVED`, `qty_received` 20, saldo +20. GR kedua 35 unit ditolak `OVER_RECEIPT` karena total 55. GR kedua 30 unit diposting: PO otomatis `RECEIVED`, saldo +30 |
| AC-07 | GR `DRAFT` gagal diposting di langkah mana pun (misalnya penulisan ledger atau audit): status tetap `DRAFT`, saldo dan `qty_received` tidak berubah, tidak ada baris ledger atau audit yang tersisa |
| AC-13 | GR `DRAFT` 10 unit diposting oleh dua permintaan bersamaan: tepat satu berhasil, saldo dan `qty_received` PO bertambah 10 saja, yang lain ditolak `INVALID_STATE_TRANSITION` |

**Titik perluasan**

- Retur dan pembalikan GR (OOS-06) menambah status dan aturan di RCV, tipe pergerakan baru di INV, dan kontrak tulis balik ke PUR; modul lain tidak berubah.

### TRF — Transfer Stok

TRF memindahkan barang antar gudang atau antar lokasi dalam dua tahap fisik, kirim lalu terima, sehingga stok dalam perjalanan selalu terlihat.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-06, bagian 5.1 (Transfer), 5.2 butir 2, 6.3, 6.7; AC-02, AC-03, AC-06, AC-09 |
| Peta kode | `api/routes/stock_transfers.py`, `services/transfer_service.py`, `repositories/transfer_repo.py`, schema `stock_transfer`, migrasi 005 (bagian transfer) |
| Bergantung pada | Tulis: `apply_movement` (INV), `next_number` (PLT). Baca: `validate_location` (WHS). Lintas-lapisan: `authorize`, `record` |
| Dipakai oleh | Baca: INV (`in_transit`), RPT |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| TRF-F01 | Pembuatan Transfer antar gudang atau antar lokasi | P0 | FR-06 |
| TRF-F02 | Persetujuan oleh Warehouse Manager gudang asal | P0 | 5.1 |
| TRF-F03 | Pengiriman yang mengurangi stok asal | P0 | FR-06 |
| TRF-F04 | Penerimaan dengan selisih yang menambah stok tujuan | P0 | FR-06 |
| TRF-F05 | Stok dalam perjalanan lewat kontrak baca `in_transit` | P0 | FR-03 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| TRF-BR01 | Header memuat gudang dan lokasi asal, gudang dan lokasi tujuan, serta catatan; minimal satu baris (barang, `qty` lebih dari 0). Skema database membatasi satu barang satu baris per Transfer, sedangkan v2.0 tidak menyebutnya (OQ-04) | FR-06 |
| TRF-BR02 | Pasangan (gudang, lokasi) asal tidak boleh sama dengan pasangan tujuan. Transfer antar lokasi dalam gudang yang sama memakai dua tahap yang sama | 6.3, FR-06 |
| TRF-BR03 | Pengiriman mengurangi stok asal sebesar `qty` lewat `apply_movement` bertipe `OUT_TRANSFER`; ditolak bila stok kurang (INV-BR03) atau lokasi asal dibekukan (INV-BR04). Sejak itu barang berstatus dalam perjalanan | FR-06, 6.1 |
| TRF-BR04 | Penerimaan adalah aksi final satu kali per dokumen (OOS-08). Pengguna mengisi `qty_received` per baris dengan `0 <= qty_received <= qty`; melebihi `qty` ditolak 409 `TRANSFER_QTY_EXCEEDS_SHIPPED` | FR-06, 6.7 |
| TRF-BR05 | `qty_received` kurang dari `qty` (termasuk 0) mewajibkan `variance_reason`; bila kosong ditolak 422 `VALIDATION_ERROR` | FR-06, 6.7 |
| TRF-BR06 | Selisih tidak dikembalikan ke gudang asal dan tidak menambah stok mana pun. Selisih tersimpan pada baris Transfer, tidak menghasilkan baris ledger, dan terbaca dari pasangan `OUT_TRANSFER` dan `IN_TRANSFER` | FR-06, 6.7 |
| TRF-BR07 | Penerimaan menambah stok tujuan sebesar `qty_received` lewat `IN_TRANSFER`, hanya untuk baris dengan `qty_received` lebih dari 0. Lokasi tujuan harus aktif dan tidak dibekukan (INV-BR04); Transfer `SHIPPED` tetap dalam perjalanan sampai lokasi tujuan tidak lagi dibekukan | 5.1, 6.6 |
| TRF-BR08 | Penugasan gudang: `transfer:create`, `transfer:approve`, dan `transfer:ship` memerlukan penugasan di gudang asal; `transfer:receive` memerlukan penugasan di gudang tujuan (IAM-BR13) | 3.2 |
| TRF-BR09 | Kontrak `in_transit` menjumlahkan `qty` baris Transfer berstatus `SHIPPED` yang belum `RECEIVED` | FR-03 |

**Status dan transisi**

| Transisi | Pemicu | Syarat | Efek |
| --- | --- | --- | --- |
| baru → `DRAFT` | `transfer:create` | TRF-BR02; lokasi valid dan aktif | Rencana dibuat; belum memengaruhi stok |
| `DRAFT` → `APPROVED` | `transfer:approve` | Minimal satu baris, `qty` lebih dari 0 | Disetujui; belum memengaruhi stok |
| `DRAFT` atau `APPROVED` → `CANCELLED` | `transfer:create` (untuk `DRAFT`), `transfer:approve` (untuk `APPROVED`) | Tidak ada | Dibatalkan |
| `APPROVED` → `SHIPPED` | `transfer:ship` | TRF-BR03 | Stok asal berkurang, ledger `OUT_TRANSFER`, barang dalam perjalanan |
| `SHIPPED` → `RECEIVED` | `transfer:receive` | TRF-BR04, TRF-BR05, TRF-BR07 | Stok tujuan bertambah, ledger `IN_TRANSFER`. Status final |

**Permission dan API**

- Permission milik TRF: `transfer:create`, `transfer:approve`, `transfer:ship`, `transfer:receive`, `transfer:read`.
- `GET/POST /stock-transfers`, `GET/PATCH /stock-transfers/{id}`, `POST /stock-transfers/{id}/approve`, `/ship`, `/receive`, `/cancel`.
- Pembuatan: `{source_warehouse_id, source_location_id, destination_warehouse_id, destination_location_id, notes, lines: [{item_id, qty}]}`. Penerimaan: `{lines: [{line_id, qty_received, variance_reason}]}`. Filter daftar: `warehouse_id`, `source_warehouse_id`, `destination_warehouse_id`, `status`, `date_from`, `date_to`, `search`.

**Kriteria penerimaan**

| AC | Skenario ringkas |
| --- | --- |
| AC-02 | Saldo Barang Y di Gudang A 10 unit, `allow_negative_stock = FALSE`, Transfer 12 unit `APPROVED`. Dikirim: ditolak `INSUFFICIENT_STOCK`, saldo tetap 10, status tetap `APPROVED` |
| AC-03 | Transfer 15 unit Gudang A ke B `APPROVED`. `SHIPPED`: stok A berkurang 15, satu baris `OUT_TRANSFER`, stok B belum bertambah. `RECEIVED` dengan `qty_received` 15: stok B bertambah 15, satu baris `IN_TRANSFER` |
| AC-06 | Saldo Barang Y di Lokasi A1 10 unit, dua Transfer masing-masing 8 unit `APPROVED`, dikirim bersamaan: tepat satu berhasil, satu ditolak `INSUFFICIENT_STOCK`, saldo akhir 2, satu baris `OUT_TRANSFER` |
| AC-09 | Transfer 25 unit `SHIPPED`. Diterima 23 tanpa alasan: ditolak 422. Diterima 23 dengan alasan: stok tujuan +23, satu baris `IN_TRANSFER` sebesar 23, selisih 2 tersimpan pada baris. Diterima 26: ditolak `TRANSFER_QTY_EXCEEDS_SHIPPED` |

**Titik perluasan**

- Penerimaan bertahap (OOS-08) mengubah TRF-BR04 dan tergolong perubahan besar di TRF; INV tidak berubah karena tipe `IN_TRANSFER` sudah ada.

### OPN — Stock Opname

OPN merekonsiliasi stok sistem dengan hitung fisik, membekukan lokasi selama penghitungan, dan menjadi jalan tunggal untuk saldo awal dan koreksi.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 1.0 · MVP |
| Asal v2.0 | FR-07, bagian 5.1 (Opname), 5.2 butir 3 dan 4, 6.6; AC-04, AC-10 |
| Peta kode | `api/routes/stock_opnames.py`, `services/opname_service.py`, `repositories/opname_repo.py` (termasuk query pembekuan lokasi), schema `stock_opname`, migrasi 005 (bagian opname) |
| Bergantung pada | Tulis: `apply_movement` (INV), `next_number` (PLT). Baca: `validate_location` (WHS). Lintas-lapisan: `authorize`, `record` |
| Dipakai oleh | Baca: INV (`is_location_frozen`), RPT |

**Fitur**

| ID | Fitur | Prioritas | Asal |
| --- | --- | :-: | --- |
| OPN-F01 | Sesi opname per gudang atau per lokasi | P0 | FR-07 |
| OPN-F02 | Potret stok sistem dan pembekuan lokasi saat sesi dimulai | P0 | FR-07, 6.6 |
| OPN-F03 | Input hitung fisik dan pengajuan persetujuan | P0 | FR-07 |
| OPN-F04 | Persetujuan atau penolakan, dan penyesuaian stok | P0 | FR-07 |
| OPN-F05 | Saldo awal stok lewat opname | P0 | FR-03 |
| OPN-F06 | Kontrak baca `is_location_frozen` | P0 | 6.6 |

**Aturan bisnis**

| ID | Aturan | Asal |
| --- | --- | --- |
| OPN-BR01 | Sesi mencakup satu gudang, dengan opsi dibatasi pada satu lokasi; `location_id` kosong berarti seluruh gudang | FR-07 |
| OPN-BR02 | Pada satu lokasi hanya boleh ada satu sesi aktif (`IN_PROGRESS` atau `WAITING_APPROVAL`). Memulai sesi ditolak bila ada sesi aktif lain pada lokasi dalam cakupan | FR-07, 5.1 |
| OPN-BR03 | Saat sesi dimulai, sistem mengambil potret saldo (`qty_system`) seluruh saldo dalam cakupan. Nilai ini dari server dan tidak dapat diedit | FR-07 |
| OPN-BR04 | Petugas mengisi `qty_physical` sebesar 0 atau lebih per baris. Barang yang ditemukan tanpa saldo ditambahkan sebagai baris baru dengan `qty_system = 0`. `qty_variance = qty_physical − qty_system`. Pengajuan persetujuan hanya setelah seluruh baris terisi | FR-07 |
| OPN-BR05 | Lokasi dalam cakupan sesi `IN_PROGRESS` atau `WAITING_APPROVAL` dianggap dibekukan: posting GR, pengiriman Transfer dari lokasi itu, dan penerimaan Transfer ke lokasi itu ditolak `LOCATION_FROZEN` (penegakan: INV-BR04). Pembekuan dilepas saat sesi `COMPLETED` atau `CANCELLED` | 6.6 |
| OPN-BR06 | Saat `COMPLETED`, setiap baris dengan selisih tidak nol disamakan saldonya dengan `qty_physical` dan menulis ledger `ADJUSTMENT_PLUS` atau `ADJUSTMENT_MINUS`; baris berselisih 0 tidak menulis ledger. Penyesuaian dikecualikan dari INV-BR04 dan tidak pernah membuat saldo negatif karena `qty_physical` tidak negatif | FR-07, 6.1 |
| OPN-BR07 | Penolakan mewajibkan alasan dan mengembalikan sesi ke `IN_PROGRESS` untuk dihitung ulang; pembekuan tetap berlaku | FR-07 |
| OPN-BR08 | Saldo awal gudang baru dimasukkan lewat opname: baris dengan `qty_system = 0` dan `qty_physical` terisi, setelah disetujui tercatat sebagai `ADJUSTMENT_PLUS`. Koreksi atas GR yang salah juga lewat opname (RCV-BR08) | FR-03, 5.2 |
| OPN-BR09 | Penugasan gudang yang diperiksa adalah gudang sesi (IAM-BR13) untuk `opname:manage`, `opname:count`, dan `opname:approve` | 3.2 |

**Status dan transisi**

| Transisi | Pemicu | Syarat | Efek |
| --- | --- | --- | --- |
| baru → `DRAFT` | `opname:manage` | Gudang dan lokasi aktif | Penjadwalan opname |
| `DRAFT` → `IN_PROGRESS` | `opname:manage` | OPN-BR02 | Mengambil potret `qty_system` dan membekukan lokasi (OPN-BR05) |
| `DRAFT` → `CANCELLED` | `opname:manage` | Tidak ada | Opname dibatalkan |
| `IN_PROGRESS` → `WAITING_APPROVAL` | `opname:count` | Seluruh baris punya `qty_physical` | Menunggu tinjauan Warehouse Manager; pembekuan tetap |
| `IN_PROGRESS` → `CANCELLED` | `opname:manage` | Tidak ada | Pembekuan dilepas; stok tidak berubah |
| `WAITING_APPROVAL` → `COMPLETED` | `opname:approve` | Tidak ada | OPN-BR06; pembekuan dilepas. Status final |
| `WAITING_APPROVAL` → `IN_PROGRESS` | `opname:approve` | Alasan penolakan wajib | Dihitung ulang oleh petugas |

**Permission dan API**

- Permission milik OPN: `opname:manage`, `opname:count`, `opname:approve`, `opname:read`.
- `GET/POST /stock-opnames`, `GET/PATCH /stock-opnames/{id}`, `POST /stock-opnames/{id}/start`, `/count`, `/lines` (POST dan PUT), `/submit`, `/approve`, `/reject`, `/cancel`.
- Pembuatan: `{warehouse_id, location_id?, notes}`. Pembaruan: `{location_id?, clear_location?, notes?}`. Penolakan: `{rejection_reason}`. Filter daftar: `warehouse_id`, `location_id`, `status`, `date_from`, `date_to`, `search`.

**Kriteria penerimaan**

| AC | Skenario ringkas |
| --- | --- |
| AC-04 | `qty_system` 100 dan `qty_physical` 97, lalu Warehouse Manager menyetujui: `qty_variance` −3, saldo menjadi 97, ledger `ADJUSTMENT_MINUS` dengan `qty_change` −3, `qty_before` 100, `qty_after` 97 |
| AC-10 | Sesi `IN_PROGRESS` pada Lokasi X: posting GR ke X atau pengiriman Transfer dari X ditolak `LOCATION_FROZEN`. Setelah sesi `COMPLETED` atau `CANCELLED`, transaksi pada X dapat dilakukan kembali |

**Titik perluasan**

- Modul yang mengurangi atau menambah stok di masa depan, seperti ISS, otomatis tunduk pada pembekuan karena melewati `apply_movement`; OPN tidak perlu diubah.

### ISS — Goods Issue (Usulan)

ISS adalah usulan modul pengeluaran barang ke pelanggan, produksi, atau pemakaian internal; ia belum disetujui dan belum memiliki aturan bisnis yang mengikat.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 0.1 · Usulan |
| Asal | OOS-05; deskripsi proyek ("penerimaan dan pengeluaran barang"); PRD v2.0 bagian 2.2 yang merekomendasikannya sebagai fase berikutnya |
| Peta kode | Belum ada; mengikuti pola modul lain (route, service, repository, schema, migrasi baru) |
| Bergantung pada | Tulis: `apply_movement` (INV), `next_number` (PLT). Baca: `validate_location` (WHS). Lintas-lapisan: `authorize`, `record` |
| Dipakai oleh | Baca: RPT |

Karena ISS wajib mengubah stok lewat `apply_movement`, beberapa perilakunya sudah tetap tanpa keputusan baru: stok tidak boleh negatif bila gudang melarangnya (INV-BR03), lokasi beku ditolak (INV-BR04), satu aksi satu transaksi (GBR-03), dan urutan kunci mengikuti GBR-07. Hal yang masih harus diputuskan dicatat di OQ-02.

**Dampak bila ISS disetujui**

| Modul | Perubahan yang diperlukan |
| --- | --- |
| PLT | Prefix baru di registri dan migrasi `CHECK` `doc_type` pada `document_sequences` |
| INV | Tipe pergerakan baru berarah negatif dan `reference_type` baru; migrasi `CHECK` `movement_type`, `reference_type`, arah tanda, dan pasangan tipe-referensi pada `stock_movements` |
| IAM | Permission baru lewat migrasi seed baru, dan menu baru bila ada halamannya |
| Aturan Bisnis Global | Satu baris baru di registri status non-final |
| MST, WHS | `open_references` mencakup dokumen ISS |
| PUR, RCV, TRF, OPN, AUD | Tidak berubah |

### RPT — Pelaporan (Usulan)

RPT adalah usulan lapisan laporan baca-saja di atas data modul lain, tanpa tabel sendiri dan tanpa kontrak tulis.

| Atribut | Isi |
| --- | --- |
| Versi / Status | 0.1 · Usulan |
| Asal | Deskripsi proyek ("pembuatan laporan"); v2.0 tidak memiliki modul pelaporan |
| Peta kode | Belum ada |
| Bergantung pada | Baca: kontrak baca INV, PUR, RCV, TRF, OPN. Lintas-lapisan: `authorize` |
| Dipakai oleh | Tidak ada |

Batasan yang sudah tetap dari arsitektur: RPT tidak mengubah data (BND-02), tidak menciptakan aturan bisnis baru karena angkanya berasal dari data modul pemilik, dan tunduk pada penugasan gudang (IAM-BR15) serta pagination (GBR-09).

**Kandidat laporan** (perlu dikonfirmasi, OQ-02)

| Laporan | Sumber data |
| --- | --- |
| Posisi stok per gudang dan lokasi, termasuk dalam perjalanan | INV, TRF |
| Kartu stok per barang | Ledger INV |
| PO yang belum terpenuhi | PUR, RCV |
| Selisih penerimaan Transfer | TRF |
| Selisih hasil Stock Opname | OPN |

## Alur Proses End-to-End

Stok berubah lewat tiga alur dokumen, dan setiap alur berakhir di satu pintu yang sama, `apply_movement` milik INV.

&#91;embedded content: alur stok · 3 alur dokumen, 1 pintu perubahan\]

Gambar menunjukkan siapa menggerakkan tiap tahap. Syarat dan penolakan tiap transisi ada di tabel status modul masing-masing, jadi tabel berikut hanya merangkai modul yang terlibat.

| Alur | Modul yang terlibat, berurutan | Ledger | Penolakan khas |
| --- | --- | --- | --- |
| Pengadaan sampai penerimaan | PUR menerbitkan PO, RCV membuat dan memposting GR, INV menambah stok, PUR memperbarui status PO lewat `apply_receipt` | `IN_PURCHASE` | `OVER_RECEIPT`, `LOCATION_FROZEN`, `WAREHOUSE_NOT_ASSIGNED` |
| Transfer stok | TRF membuat dan menyetujui, TRF mengirim dan INV mengurangi stok asal, TRF menerima dan INV menambah stok tujuan | `OUT_TRANSFER`, `IN_TRANSFER` | `INSUFFICIENT_STOCK`, `LOCATION_FROZEN`, `TRANSFER_QTY_EXCEEDS_SHIPPED` |
| Stock opname | OPN memulai dan membekukan lokasi, petugas menghitung, OPN menyetujui dan INV menyamakan saldo | `ADJUSTMENT_PLUS`, `ADJUSTMENT_MINUS` | `INVALID_STATE_TRANSITION` bila sesi aktif lain sudah ada pada lokasi |
| Saldo awal dan koreksi | Dikerjakan sebagai opname dengan `qty_system = 0` (OPN-BR08); koreksi GR yang salah memakai alur yang sama (RCV-BR08) | `ADJUSTMENT_PLUS` | Sama dengan alur opname |
| Pendaftaran tenant baru | TNT membuat tenant dan paketnya, IAM menyalin peran bawaan dan membuat Super Admin pertama, CFG menyiapkan pengaturan, AUD mencatat; semuanya satu transaksi | Tidak ada | `DUPLICATE` bila slug sudah dipakai |
| Akses oleh tenant ditangguhkan | IAM membaca tenant\_status pada login, refresh, dan setiap request; permintaan ditolak sebelum menyentuh modul lain | Tidak ada | `TENANT_SUSPENDED` |

Dua aturan lintas alur perlu diingat: lokasi yang sedang diopname menolak GR dan Transfer (OPN-BR05), dan seluruh langkah satu aksi berjalan dalam satu transaksi (GBR-03), sehingga tidak ada keadaan setengah jadi yang terlihat.

## Model Data Konseptual

Setiap tabel dimiliki satu modul; tabel milik modul lain hanya ditulis lewat kontrak yang tercatat. DDL lengkap ada di `SCHEMA_DATABASE.MD` dan mengikuti tabel ini.

| Tabel | Pemilik | Penulis lain (lewat kontrak) | Merujuk ke modul lain |
| --- | --- | --- | --- |
| `roles`, `permissions`, `role_permissions` | IAM | Tidak ada | Tidak ada |
| `users` | IAM | Tidak ada | Tidak ada |
| `user_warehouses` | IAM | Tidak ada | WHS (`warehouses`) |
| `refresh_tokens` | IAM | Tidak ada | Tidak ada |
| `menus` | IAM | Tidak ada | Tidak ada (`permissions` milik IAM sendiri) |
| `categories`, `uoms`, `suppliers` | MST | Tidak ada | Tidak ada |
| `items` | MST | Tidak ada | Tidak ada |
| `warehouses` | WHS | Tidak ada | Tidak ada |
| `storage_locations` | WHS | Tidak ada | Tidak ada |
| `inventory_balances` | INV | Hanya lewat `apply_movement` | WHS, MST |
| `stock_movements` (append-only) | INV | Hanya lewat `apply_movement` | WHS, MST, IAM |
| `purchase_orders` | PUR | Tidak ada | MST (`suppliers`), WHS |
| `po_lines` | PUR | RCV, hanya kolom `qty_received` lewat `apply_receipt` | MST (`items`) |
| `goods_receipts` | RCV | Tidak ada | PUR (`purchase_orders`, komposit dengan gudang) |
| `gr_lines` | RCV | Tidak ada | PUR (`po_lines`), WHS (`storage_locations`) |
| `stock_transfers` | TRF | Tidak ada | WHS (gudang dan lokasi asal serta tujuan) |
| `stock_transfer_lines` | TRF | Tidak ada | MST (`items`) |
| `stock_opnames` | OPN | Tidak ada | WHS |
| `stock_opname_lines` | OPN | Tidak ada | MST (`items`), WHS (`storage_locations`) |
| `audit_logs` (append-only) | AUD | Semua modul, hanya lewat `record` | IAM (`users`) |
| `document_sequences` | PLT | PUR, RCV, TRF, OPN, hanya lewat `next_number` | Tidak ada |
| `schema_migrations` | PLT | Hanya runner migrasi | Tidak ada |
| `tenants`, `plans`, `platform_admins` | TNT | Tidak ada | Tidak ada |
| `settings` | CFG | TNT, hanya lewat `seed_tenant_settings` | WHS (`warehouses`, untuk tingkat gudang) |

Kolom `created_by` pada hampir semua tabel merujuk ke `users` milik IAM; ini referensi identitas, bukan dependensi tulis.

Semua tabel di atas milik tenant dan memuat `tenant_id` yang merujuk ke `tenants` (TNT), kecuali `permissions`, `menus`, `plans`, `tenants`, `platform_admins`, dan `schema_migrations` yang bersifat global dan tidak menyimpan data bisnis. Kunci asing antar-tabel milik tenant bersifat komposit `(tenant_id, id)` (GBR-16).

### Integritas lintas modul yang dijaga database

- Composite foreign key `(location_id, warehouse_id)` ke `storage_locations` pada saldo, ledger, baris GR, Transfer, dan Opname menjamin dokumen satu gudang tidak dapat menyentuh lokasi gudang lain (WHS-BR03).
- `goods_receipts` merujuk `(po_id, warehouse_id)` ke `purchase_orders`, sehingga gudang GR pasti sama dengan gudang PO; `gr_lines` merujuk `(po_line_id, po_id)` sehingga baris GR hanya menunjuk baris PO dari PO yang sama.
- `stock_movements` memiliki `CHECK` untuk tipe, arah tanda, kesesuaian tipe dengan `reference_type`, dan `qty_after = qty_before + qty_change` (INV-BR02).
- `po_lines` membatasi `0 <= qty_received <= qty_ordered` (PUR-BR03).

### Pemetaan berkas migrasi ke modul

Satu berkas migrasi boleh memuat beberapa modul, tetapi modul baru selalu memakai berkas baru (PLT-BR03).

| Berkas | Isi | Modul |
| --- | --- | --- |
| `001_create_auth_tables.sql` | Peran, permission, pengguna, refresh token | IAM |
| `002_create_master_tables.sql` | Kategori, UoM, pemasok, barang, gudang, lokasi, penugasan gudang | MST, WHS, IAM |
| `003_create_inventory_tables.sql` | Saldo dan ledger | INV |
| `004_create_purchasing_tables.sql` | PO dan GR | PUR, RCV |
| `005_create_transfer_opname.sql` | Transfer dan Opname | TRF, OPN |
| `006_create_audit_sequences.sql` | Audit log dan penomoran dokumen | AUD, PLT |
| `007_append_only_guards.sql` | Trigger dan hak role `wms_app` | INV, AUD |
| `008_seed_roles_permissions.sql` | Lima peran dan 24 permission beserta pemetaannya | IAM |
| `009_create_menu_tables.sql` | Tabel menu dan menu awal | IAM |
| `010_create_tenants_settings.sql` | Tenant, paket, Platform Admin, pengaturan, dan empat permission baru | TNT, CFG, IAM |
| `011_add_tenant_scope.sql` | Kolom `tenant_id`, kunci asing komposit, keunikan per tenant, dan RLS pada seluruh tabel milik tenant; tenant bawaan untuk data yang sudah ada | PLT, semua modul |

Penempatan `user_warehouses` mengikuti `SCHEMA_DATABASE.MD` (berkas 002); `FOLDER_STRUCTURE.MD` menempatkannya di 001 (OQ-08).

## Kebutuhan Non-Fungsional

Sembilan kebutuhan non-fungsional berlaku lintas modul; tiap baris menyebut modul yang bertanggung jawab agar tidak ada yang tak bertuan.

| ID | Kebutuhan | Ukuran atau ketentuan | Penanggung jawab | Asal v2.0 |
| --- | --- | --- | --- | --- |
| NFR-01 | Integritas transaksional | Status dokumen, saldo, ledger, dan audit log satu aksi berada dalam satu transaksi; gagal di mana pun berarti rollback total (GBR-03) | Semua modul | 7.1 |
| NFR-02 | Keamanan | Kata sandi Argon2id atau bcrypt, minimal 8 karakter. JWT HS256 dengan kunci minimal 32 byte dari variabel lingkungan. Semua SQL berparameter. Rahasia tidak disimpan di repositori. Kata sandi dan token tidak masuk log. TLS diterminasi di reverse proxy. Database memisahkan role pemilik skema dan role aplikasi | IAM, PLT | 7.2 |
| NFR-03 | Kinerja | Baca saldo stok dan cari master data di bawah 200 ms pada persentil ke-95. Asumsi beban awal, dapat disesuaikan: 20 pengguna bersamaan, 10.000 barang aktif, 1.000.000 baris ledger. Semua daftar dipaginasi | INV, MST, PLT | 7.3 |
| NFR-04 | Presisi numerik | Kuantitas `NUMERIC(18,4)`, `Decimal` di Python, string desimal di JSON (GBR-05) | INV, PLT | 7.4 |
| NFR-05 | Akses data dan migrasi | PostgreSQL langsung lewat `psycopg` 3 dengan connection pool, tanpa ORM; SQL hanya di lapisan repository; migrasi `.sql` forward-only; kunci utama `BIGINT GENERATED ALWAYS AS IDENTITY`; waktu `TIMESTAMPTZ` UTC | PLT | 7.5 |
| NFR-06 | Operasional | Log terstruktur dengan `X-Request-ID`, `GET /health`, dokumentasi OpenAPI otomatis dari FastAPI | PLT | 7.6 |
| NFR-07 | Kualitas | Setiap AC diuji pada PostgreSQL sungguhan, bukan mock. AC-06 dan AC-13 memakai beberapa koneksi terpisah sehingga data direset antar test, bukan rollback per test. AC-08 dijalankan dengan role `wms_app`. Nama fungsi test memuat kode AC-nya | Semua modul | 7.6, FOLDER\_STRUCTURE bagian 8 |
| NFR-08 | Isolasi tenant | Setiap tabel milik tenant memiliki `tenant_id` NOT NULL, indeks berawalan `tenant_id`, dan RLS aktif dengan FORCE; role `wms_app` tidak memiliki BYPASSRLS. Test otomatis memindai katalog skema dan gagal bila ada tabel di luar daftar tabel global yang tidak memuat `tenant_id` (GBR-16) | PLT, TNT, semua modul | Baru v3.1 |
| NFR-09 | Keadilan antar-tenant | Semua daftar dipaginasi (GBR-09) dan memakai indeks berawalan tenant\_id; batas laju per tenant mencegah satu tenant menghabiskan kapasitas. Beban awal NFR-03 berlaku per tenant; kapasitas total mengikuti AS-03 | PLT, TNT | Baru v3.1 |

## Roadmap dan Prioritas

MVP mencakup dua belas modul, dibangun dari fondasi ke atas sesuai lapisan dependensi; urutan ini mengikuti tahap M0 sampai M8 di `FOLDER_STRUCTURE.MD` dan belum memuat tanggal karena jadwal belum ditetapkan.

| Fase | Modul | Prasyarat | Selesai bila |
| --- | --- | --- | --- |
| 0 Fondasi | PLT dengan konteks tenant, seluruh skema ber-tenant\_id (migrasi 001 sampai 011) | Tidak ada | `GET /health` hidup, migrasi berjalan, `UPDATE` pada `stock_movements` lewat role `wms_app` ditolak, dan pemindaian skema tidak menemukan tabel bisnis tanpa tenant\_id (NFR-08) |
| 1 Tenant, akses, dan audit | TNT, CFG, IAM, AUD | Fase 0 | AC-05, AC-11, AC-14, AC-15, AC-16, AC-17 lulus |
| 2 Master dan gudang | MST, WHS | Fase 1 | Penugasan gudang berfungsi; sisi akses AC-12 serta AC-18 dan AC-19 lulus |
| 3 Inti stok | INV | Fase 2 | `apply_movement` diuji dua thread: penguncian bekerja |
| 4 Pengadaan | PUR, RCV | Fase 3 | AC-01, AC-07, AC-13 lulus |
| 5 Transfer | TRF | Fase 3 | AC-02, AC-03, AC-06, AC-09 lulus |
| 6 Opname | OPN | Fase 3 | AC-04, AC-10 lulus |
| 7 Pengerasan | Semua | Fase 4, 5, 6 | AC-01 sampai AC-21 lulus; baca stok di bawah 200 ms pada data uji (NFR-03) |

Fase 4, 5, dan 6 tidak saling bergantung dan dapat dikerjakan paralel setelah INV selesai.

### Setelah MVP

| Kandidat | Status | Syarat sebelum dikerjakan |
| --- | --- | --- |
| ISS Goods Issue | Usulan | Keputusan di OQ-02, lalu daftar dampak pada spesifikasi ISS dijalankan |
| RPT Pelaporan | Usulan | Daftar laporan dikonfirmasi (OQ-02) |
| OOS-01 sampai OOS-10 | Di luar lingkup | Dinilai satu per satu memakai kolom modul terdampak; tidak ada urutan prioritas yang ditetapkan |
| P1 Siklus barang lengkap: ISS Goods Issue, RPT dasar (kartu stok, posisi stok, riwayat pergerakan, stok menipis), ekspor CSV dan Excel | Usulan | Keputusan OQ-02; MVP selesai |
| P2 Fleksibilitas lintas industri: atribut barang dinamis, pelacakan opsional (batch, kedaluwarsa, nomor seri), konversi satuan, hierarki lokasi yang dapat diatur | Usulan | Dinilai lewat OOS-01, OOS-02, OOS-07; RSK-02 (kunci saldo) diputuskan lebih dulu; saklar pelacakan didaftarkan sebagai kunci CFG (BND-08) |
| P3 Kontrol stok: titik pesan ulang dan notifikasi stok menipis, retur, persetujuan berambang untuk penyesuaian besar | Usulan | P1 selesai; OOS-06 dan OOS-09 dinilai |
| P4 Operasional gudang: barcode dan QR, saran lokasi simpan (putaway), daftar ambil (picking) | Usulan | P1 selesai; OOS-10 dinilai |
| P5 Penjualan dan nilai persediaan: Sales Order, reservasi stok, valuasi FIFO atau rata-rata | Usulan | OOS-03 dan OOS-04 dinilai; menyentuh INV sehingga ditandai perubahan besar (MAJOR) |
| P6 Integrasi dan analitik: webhook atau event stok, notifikasi email dan WhatsApp, API key, impor massal, dasbor perputaran barang | Usulan | P1 selesai; OOS-10 dinilai |
| P7 Platform SaaS: penagihan dan langganan, pendaftaran mandiri, SSO dan 2FA per tenant, domain khusus, ekspor data tenant | Usulan | OOS-11 sampai OOS-15 dinilai; OQ-13, OQ-14, OQ-15 diputuskan |

Kandidat P1 sampai P7 diurutkan menurut ketergantungan dan nilai, dan dapat ditambahkan bertahap karena tiap kandidat berupa modul atau fitur baru yang menulis stok lewat `apply_movement` dan mengikuti GBR-16 sejak desain. Kunci pengaturan baru didaftarkan di CFG, bukan dicabangkan di kode.

## Keterlacakan dan Riwayat Perubahan

Setiap bagian PRD v2.0 punya tempat baru yang tercatat di sini, sehingga dokumen lain yang masih menyebut nomor bagian lama (misalnya "PRD 6.5") dapat diterjemahkan ke ID.

### Peta bagian v2.0 ke ID v3.0

| v2.0 | Lokasi dan ID baru |
| --- | --- |
| 1 Tujuan sistem | Tujuan G-01 sampai G-04 |
| 2.1 In-scope, 2.2 Out-of-scope | Katalog modul; OOS-01 sampai OOS-10 |
| 3, 3.1 Peran dan matriks permission | Pengguna dan Peran; kolom Modul pemilik |
| 3.2 Warehouse scoping | IAM-BR12 sampai IAM-BR15; aturan penugasan di RCV-BR09, TRF-BR08, OPN-BR09 |
| FR-01 Autentikasi dan menu | IAM-F01 sampai IAM-F09; IAM-BR01 sampai IAM-BR11 |
| FR-02 Master data | MST-F01 sampai MST-F05; MST-BR01 sampai MST-BR05; WHS-F01 sampai WHS-F02; WHS-BR01 sampai WHS-BR04 |
| FR-03 Multi-gudang dan stok | INV-F01, INV-F02; INV-BR01, INV-BR06; OPN-BR08 |
| FR-04 Purchase Order | PUR-F01 sampai PUR-F03; PUR-BR01 sampai PUR-BR09 |
| FR-05 Goods Receipt | RCV-F01 sampai RCV-F04; RCV-BR01 sampai RCV-BR07 |
| FR-06 Transfer Stok | TRF-F01 sampai TRF-F04; TRF-BR01 sampai TRF-BR07 |
| FR-07 Stock Opname | OPN-F01 sampai OPN-F04; OPN-BR01 sampai OPN-BR07 |
| FR-08 Ledger | INV-F03; INV-BR02; registri tipe pergerakan |
| FR-09 Audit log | AUD-F01, AUD-F02; AUD-BR01 sampai AUD-BR03 |
| FR-10 Penomoran dokumen | PLT-F01; PLT-BR01, PLT-BR02; GBR-08 |
| FR-11 Pencarian dan pagination | PLT-F02; GBR-09 |
| 5.1 Siklus status | Tabel Status dan transisi di PUR, RCV, TRF, OPN; GBR-04 |
| 5.2 Rincian alur | Alur Proses End-to-End; AC-01 sampai AC-04 |
| 5.3 Jenis pergerakan | Registri tipe pergerakan di INV |
| 6.1 Stok negatif | INV-BR03, INV-F05 |
| 6.2 Over-receipt | RCV-BR04, RCV-BR05 |
| 6.3 Validasi lokasi dan gudang | GBR-11; WHS-BR03; TRF-BR02; PUR-BR02 |
| 6.4 Imutabilitas | GBR-02; AUD-BR04 |
| 6.5 Konkurensi | GBR-04, GBR-07; INV-BR01, INV-BR05 |
| 6.6 Pembekuan lokasi | OPN-BR05; INV-BR04 |
| 6.7 Selisih penerimaan Transfer | TRF-BR04 sampai TRF-BR06 |
| 6.8 Penonaktifan master | GBR-13; MST-BR03, MST-BR05; WHS-BR04 |
| 6.9 Kuantitas dan presisi | GBR-05 |
| 7.1 sampai 7.6 | NFR-01 sampai NFR-07 (v2.0) dan NFR-08, NFR-09 (v3.1) |
| 8 Kriteria penerimaan | AC-01 sampai AC-14 (v2.0) dan AC-15 sampai AC-21 (v3.1), dimiliki modul seperti tabel berikut |
| Lampiran A Entitas data | Model Data Konseptual |
| Lampiran B Konvensi API dan kode error | Spesifikasi Modul (bagian API) dan Katalog kode error |
| Lampiran C Catatan revisi | Riwayat perubahan di bawah |

### Pemilik kriteria penerimaan

| AC | Modul | Berkas test (`FOLDER_STRUCTURE.MD`) |
| --- | --- | --- |
| AC-01, AC-07, AC-13 | RCV | `tests/test_goods_receipt.py` |
| AC-02, AC-03, AC-06, AC-09 | TRF | `tests/test_stock_transfer.py` |
| AC-04, AC-10 | OPN | `tests/test_stock_opname.py` |
| AC-05, AC-12 | IAM | `tests/test_rbac_scoping.py` |
| AC-11 | IAM | `tests/test_auth.py` |
| AC-14 | IAM | `tests/test_menus.py` |
| AC-08 | INV | `tests/test_immutability.py` |
| AC-15, AC-19 | TNT | `tests/test_tenant_isolation.py` |
| AC-16, AC-17, AC-18 | TNT | `tests/test_tenant_lifecycle.py` |
| AC-20, AC-21 | CFG | `tests/test_settings.py` |

### Peta kebutuhan frontend ke modul

`PRD_FRONTEND.md` memakai nomor FR sendiri. Tabel ini menunjukkan modul backend yang menjadi sumber tiap kebutuhan, agar perubahan modul langsung menunjuk halaman yang terdampak.

| Frontend | Modul backend |
| --- | --- |
| FR-01 Autentikasi dan sesi, FR-02 Navigasi dinamis, FR-10 Pengguna dan RBAC | IAM |
| FR-04 Master data | MST, WHS |
| FR-05 Saldo dan ledger | INV |
| FR-06 Purchase Order | PUR |
| FR-07 Goods Receipt | RCV |
| FR-08 Transfer | TRF |
| FR-09 Opname | OPN |
| FR-11 Audit log | AUD |
| FR-03 Dashboard informatif, FR-12 Landing page | Tidak ada; murni frontend |

### Riwayat perubahan

| Versi | Tanggal | Perubahan |
| --- | --- | --- |
| 3.1 (draf) | 2026-11-02 | Menambah keputusan SaaS multi-tenant: modul TNT dan CFG, GBR-16 sampai GBR-18, BND-07 dan BND-08, enam kontrak baru, empat permission tenant dan dua permission platform, tiga kode error, AC-15 sampai AC-21, NFR-08 dan NFR-09, OOS-11 sampai OOS-16, OQ-11 sampai OQ-17, dan roadmap pasca-MVP P1 sampai P7. Tidak ada aturan bisnis v2.0 yang diubah; tabel yang ada mendapat kolom tenant\_id |
| 3.0 (draf) | 2026-10-30 | Disusun ulang secara modular dari v2.0: 12 modul, ID tetap, kontrak antarmodul, aturan batas, dan registri bersama. Tidak ada aturan bisnis v2.0 yang diubah. Ditambahkan: modul usulan ISS dan RPT, nama peran Auditor, dan `INTERNAL_ERROR` yang ditandai Perlu Ditinjau |
| 2.0 | Sebelum 2026-10-30 | Lihat Lampiran C PRD v2.0 untuk 17 perubahan dari v1 |

### Risiko dan asumsi

| ID | Jenis | Uraian | Tindak lanjut |
| --- | --- | --- | --- |
| RSK-01 | Risiko | Dokumen turunan (`SCHEMA_DATABASE.MD`, `docs/api/`, `PRD_FRONTEND.md`) tertinggal dari PRD | Langkah 5 prosedur perubahan; dokumen turunan merujuk ID, bukan nomor bagian |
| RSK-02 | Risiko | Mengubah kunci saldo (misalnya lot atau nomor seri) menyentuh INV, RCV, TRF, dan OPN sekaligus | Ditandai perubahan besar (MAJOR) pada INV; dinilai lewat OOS-01 dan OOS-02 sebelum dikerjakan |
| RSK-03 | Risiko | Tanpa Goods Issue, stok hanya berkurang lewat Transfer dan Opname, sehingga tujuan proyek "pengeluaran barang" belum terpenuhi | Keputusan di OQ-02 |
| RSK-04 | Risiko | Refresh token frontend disimpan di `localStorage` sehingga terbuka terhadap XSS | Mitigasi dan jalur migrasi ke cookie HttpOnly ada di `PRD_FRONTEND.md` bagian 8.1 |
| AS-01 | Asumsi | Beban kerja NFR-03 (20 pengguna, 10.000 barang, 1.000.000 baris ledger) adalah asumsi awal | Ditinjau ulang setelah ada data pemakaian |
| AS-02 | Asumsi | Daftar endpoint di spesifikasi modul diambil dari PRD v2.0 Lampiran B dan `PRD_FRONTEND.md` bagian 17, bukan dari kode | Diverifikasi terhadap kode saat `docs/api/` disusun |
| RSK-05 | Risiko | Satu query tanpa filter tenant membocorkan data antar-perusahaan | RLS sebagai lapis kedua (GBR-16), pemindaian skema (NFR-08), dan AC-15 diulang untuk setiap modul baru |
| RSK-06 | Risiko | Dokumen turunan dan kode v2.0 masih satu organisasi: skema, login, token, dan `PRD_FRONTEND.md` perlu tenant | Migrasi 010 dan 011 forward-only dengan tenant bawaan untuk data lama; OQ-06 diperluas ke perubahan tenant; frontend menambah kolom slug pada login |
| AS-03 | Asumsi | Beban NFR-03 berlaku per tenant; jumlah tenant dan kapasitas total belum ditetapkan | Ditinjau ulang setelah ada tenant pertama dan data pemakaian |
| AS-04 | Asumsi | Nama kontrak, endpoint, peta kode, dan kunci pengaturan awal untuk TNT dan CFG adalah usulan desain, bukan hasil pembacaan kode | Diverifikasi bersama OQ-10 saat modul dibangun |

### Pertanyaan terbuka

| ID | Pertanyaan | Dampak |
| --- | --- | --- |
| OQ-01 | Ukuran keberhasilan bisnis apa yang dipakai, misalnya tingkat selisih opname atau lama proses penerimaan? | Melengkapi Ukuran keberhasilan |
| OQ-02 | Kapan Goods Issue dan Pelaporan masuk fase? Untuk ISS: tujuan pengeluaran (pelanggan, produksi, internal), perlu persetujuan atau tidak, dan status dokumennya. Untuk RPT: laporan mana yang dibutuhkan | ISS dan RPT berpindah dari Usulan ke Disetujui |
| OQ-03 | Master data, gudang, dan lokasi belum memiliki kriteria penerimaan; apakah perlu AC tersendiri? | MST, WHS |
| OQ-04 | Apakah satu barang hanya boleh satu baris per Transfer? Skema database menerapkannya (`UNIQUE (transfer_id, item_id)`), PRD v2.0 tidak menyebutnya | TRF-BR01 |
| OQ-05 | Apakah `INTERNAL_ERROR` (500) masuk katalog resmi? Disebut `PRD_FRONTEND.md`, tidak ada di katalog v2.0 | Katalog kode error |
| OQ-06 | `SCHEMA_DATABASE.MD` dan `FOLDER_STRUCTURE.MD` masih merujuk nomor bagian v2.0 (misalnya "PRD 6.5", "FR-05"); perlu diperbarui ke ID v3.0 | RSK-01 |
| OQ-07 | Dokumen frontend saling berbeda: `PRD_FRONTEND.md` bagian 17.5 menambah service pada `docker-compose.yml` dengan `Dockerfile.frontend`, sedangkan `FOLDER_STRUCTURE.md` bagian 6 memakai `docker-compose.dev.yml` dan `Dockerfile.dev`. `FOLDER_STRUCTURE.md` juga menyebut sesi auth dipersist oleh Zustand, sedangkan `PRD_FRONTEND.md` bagian 8 menyatakan access token hanya di memory | Konsistensi dokumen frontend |
| OQ-08 | `user_warehouses` ada di migrasi 002 menurut `SCHEMA_DATABASE.MD` tetapi di 001 menurut `FOLDER_STRUCTURE.MD` | Pemetaan migrasi |
| OQ-09 | `FOLDER_STRUCTURE.md` (frontend) dan `FOLDER_STRUCTURE.MD` (backend) hanya berbeda huruf besar pada ekstensi; perlu nama yang membedakan | Keterbacaan dokumen proyek |
| OQ-10 | Nama kontrak antarmodul belum diverifikasi terhadap kode. Hanya `apply_movement`, `is_location_frozen`, `record` (`audit_service`), `next_number` (`numbering_service`), dan `authorize` (`require_permission` dan `ensure_warehouse_access`) punya padanan di `FOLDER_STRUCTURE.MD`; `apply_receipt`, `gr_status_summary`, `in_transit`, `validate_location`, dan `open_references` adalah nama konseptual | Penamaan kontrak |
| OQ-11 | Strategi isolasi data: satu database dan skema bersama dengan tenant\_id plus RLS (usulan dokumen ini), atau skema atau database terpisah per tenant? | GBR-16, NFR-08, PLT, seluruh migrasi |
| OQ-12 | Bagaimana Platform Admin diautentikasi: tabel `platform_admins` dengan alur login terpisah, atau penerbit token yang sama dengan klaim lingkup platform? | IAM-BR20, TNT |
| OQ-13 | Tenant dibuat oleh Platform Admin saja pada MVP, atau perlu pendaftaran mandiri sejak awal? | TNT-F01, OOS-12 |
| OQ-14 | Apakah satu orang boleh menjadi pengguna di beberapa tenant dengan satu email dan memilih tenant saat login? | IAM-BR16, OOS-15 |
| OQ-15 | Berapa lama data tenant nonaktif disimpan, dan bagaimana ekspor serta penghapusan dilakukan mengingat GBR-01 melarang hapus permanen? | TNT-BR03, TNT-F06 |
| OQ-16 | Apa nama paket dan nilai batas gudang, pengguna aktif, dan barang aktif tiap paket? | TNT-F04, TNT-BR05 |
| OQ-17 | Bolehkah Platform Admin masuk sebagai tenant untuk dukungan, dengan persetujuan dan jejak audit apa? | TNT-BR06, AUD |

### Glosarium

| Istilah | Arti |
| --- | --- |
| Modul pemilik | Modul yang satu-satunya berhak mendefinisikan dan mengubah sebuah tabel, aturan, permission, atau kode error |
| Kontrak | Jalur resmi antarmodul: tulis, baca, atau lintas-lapisan |
| Registri | Tabel bersama yang diisi banyak modul tetapi punya satu pemilik, misalnya tipe pergerakan |
| Usulan | Status modul atau fitur yang belum disetujui dan belum mengikat |
| GR (Goods Receipt) | Dokumen penerimaan barang terhadap sebuah PO |
| PO (Purchase Order) | Pesanan pembelian ke pemasok |
| UoM | Satuan ukur dasar sebuah barang |
| SKU | Kode unik sebuah barang |
| Saldo | Kuantitas barang di satu lokasi pada satu gudang (`qty_on_hand`) |
| Ledger | Buku besar pergerakan stok yang tidak dapat diubah (`stock_movements`) |
| In-transit | Barang pada Transfer berstatus `SHIPPED` yang belum `RECEIVED` |
| Opname | Penghitungan fisik untuk menyamakan stok sistem dengan kenyataan |
| Pembekuan lokasi | Penolakan GR dan Transfer pada lokasi yang sedang diopname |
| Warehouse scoping | Pembatasan aksi pengguna pada gudang yang ditugaskan kepadanya |
| Append-only | Tabel yang hanya menerima baris baru; ubah dan hapus ditolak |
| Tenant | Perusahaan pelanggan yang memakai JejakStok dan pemilik tunggal seluruh data bisnisnya (TNT) |
| Slug tenant | Pengenal tenant yang unik secara global dan dipakai pada login (TNT-BR01) |
| RLS | Row Level Security PostgreSQL; lapis kedua isolasi tenant setelah filter query (GBR-16) |
| Platform Admin | Operator JejakStok yang mengelola tenant; bukan peran tenant dan tidak melihat data bisnis (TNT-BR06) |
| Pengaturan bertingkat | Nilai konfigurasi yang dicari dari gudang, lalu tenant, lalu bawaan registri (CFG-BR01) |
