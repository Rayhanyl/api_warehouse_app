# Panduan & Acuan Validasi Frontend (Sinkron dengan Backend & Database)

**Versi Dokumen:** 1.0  
**Status:** Disetujui — Acuan Resmi Implementasi UI/Form Validation  
**Rujukan Sumber Kebenaran:**
- Backend Schemas: `app/schemas/*.py`
- Backend Services: `app/services/*.py`
- Database Migrations: `db/migrations/001_*.sql` s.d. `010_harden_constraints_and_indexes.sql`
- Kontrak API & PRD: `docs/CORE/PRD_GENERAL.md`, `docs/CORE/PRD_FRONTEND.md`, `docs/CORE/API_CONTRACT.md`

---

## 1. Prinsip Utama Sinkronisasi Validasi Frontend ↔ Backend

1. **Aturan Batas Karakter (`maxLength` & `minLength`) Harus Sama Persis:**
   Atribut HTML `maxLength` pada `<input>` / `<textarea>` dan skema validasi form (Zod / React Hook Form) **wajib sama persis** dengan batas `max_length` di Pydantic Schema & `VARCHAR(N)` di PostgreSQL (tidak boleh berbeda, misalnya input `140` padahal validasi `120`).
2. **Trim Spasi Sebelum Validasi & Submit:**
   Semua input teks wajib di-`.trim()` terlebih dahulu sebelum diperiksa `minLength`, regex, maupun dikirim ke API. String yang hanya berisi spasi (`"   "`) wajib ditolak di form sebagai field kosong.
3. **Tidak Boleh Menggunakan Data Dummy/Fallback Saat Master Kosong:**
   Dropdown referensi (`category_id`, `uom_id`, `supplier_id`, `warehouse_id`, `location_id`, `item_id`, `role_id`, `permission_id`) **hanya boleh** berisi data aktif (`is_active = true`) yang diambil dari server. Jika daftar dari server kosong, tampilkan *empty state* dan tombol pintasan membuat master data terkait — **dilarang** memakai data contoh lokal.
4. **Simpan Data Hanya Setelah Respons Sukses dari Server (`200 OK` / `201 Created`):**
   Jangan langsung menambahkan data ke state lokal sebelum memanggil API. Setelah API mengembalikan `200`/`201`, perbarui state atau lakukan *invalidate/refetch* query.
5. **Kuantitas Wajib Dikirim Sebagai String Desimal (Bukan `float` Number):**
   Backend menolak tipe JSON `float` (`10.5`) pada seluruh field kuantitas untuk mencegah ketidakakuratan *floating-point*. Kirim selalu sebagai string (contoh: `"10"` atau `"10.5000"`).
6. **Form Edit (`PATCH`) Wajib Mengirim Minimal Satu Field yang Berubah:**
   Backend menolak payload `{}` kosong dengan `422 VALIDATION_ERROR`. Tombol "Simpan Perubahan" sebaiknya dinonaktifkan (`disabled`) bila belum ada field yang diubah (`!isDirty`), atau hanya mengirim field yang benar-benar berubah.

---

## 2. Standar Regex & Pola Format Global

Gunakan konstanta regex berikut di sisi Frontend agar 100% identik dengan Backend:

| Nama Pola | Regex Pattern | Aturan Tambahan | Dipakai Pada Field |
| :--- | :--- | :--- | :--- |
| **`CODE_REGEX`** | `/^[A-Za-z0-9][A-Za-z0-9._/-]*$/` | Diawali huruf/angka; hanya boleh huruf, angka, titik (`.`), garis bawah (`_`), garis miring (`/`), atau tanda hubung (`-`); **tanpa spasi**. | `uoms.code`, `suppliers.code`, `items.sku`, `warehouses.code`, `storage_locations.code`, `menus.code` |
| **`USERNAME_REGEX`** | `/^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$/` | Panjang 3–64 karakter; diawali huruf/angka; hanya boleh huruf, angka, `.`, `_`, `-`; **tanpa spasi**. | `users.username` |
| **`EMAIL_REGEX`** | `/^[^\s@]+@[^\s@]+\.[^\s@]+$/` | Wajib format email standar tanpa spasi, disimpan/dibandingkan secara *case-insensitive*. | `users.email`, `suppliers.email` (opsional) |
| **`PHONE_REGEX`** | `/^[0-9+() -]{6,30}$/` | Panjang 6–30 karakter; hanya angka, `+`, `(`, `)`, spasi, `-`; serta **wajib mengandung minimal 6 digit angka** (`value.replace(/\D/g, '').length >= 6`). | `suppliers.phone` (opsional) |
| **`ICON_REGEX`** | `/^[a-z0-9]+(-[a-z0-9]+)*$/` | Format *kebab-case* huruf kecil & angka (nama ikon Lucide, contoh: `layout-dashboard`, `package-check`). | `menus.icon` (opsional) |
| **`PATH_FORMAT`** | `/^\/\S*$/` | Wajib diawali karakter `'/'` dan tidak boleh mengandung spasi. | `menus.path` |
| **`DECIMAL_QTY_REGEX`** | `/^\d{1,14}(\.\d{1,4})?$/` | Maksimal 14 digit sebelum titik desimal dan maksimal 4 digit setelah titik desimal (`NUMERIC(18,4)`, maks `99999999999999.9999`). | `qty_ordered`, `qty_received`, `qty`, `qty_physical` |
| **`INTEGER_QTY_REGEX`** | `/^\d{1,14}$/` | Bilangan bulat tanpa desimal (atau `.0000`) bila UoM barang memiliki `allow_decimal = false`. | Semua input kuantitas untuk barang ber-UoM `allow_decimal = false` |

---

## 3. Spesifikasi Validasi Per Modul & Form

### 3.1 Autentikasi (`/api/v1/auth/*`)

#### A. Form Login (`POST /api/v1/auth/login`)
| Field | Wajib | Tipe | Min Length | Max Length | Validasi Frontend |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `username` | Ya | `string` | `1` | `64` | Trim spasi; tidak boleh kosong. |
| `password` | Ya | `string` | `1` | `255` | Tidak boleh kosong. |

- **Penanganan Error API di UI:**
  - `401 AUTH_INVALID_CREDENTIALS`: Tampilkan pesan *"Username atau kata sandi salah."*
  - `429 AUTH_TOO_MANY_ATTEMPTS`: Akun terkunci 15 menit setelah 5x gagal login; tampilkan waktu buka kunci dari `error.details.locked_until`.

#### B. Form Ganti Kata Sandi (`POST /api/v1/auth/change-password`)
| Field | Wajib | Tipe | Min Length | Max Length | Validasi Frontend |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `current_password` | Ya | `string` | `1` | `255` | Wajib diisi. |
| `new_password` | Ya | `string` | `8` | `255` | Minimal 8 karakter dan **tidak boleh hanya berisi spasi** (`new_password.trim().length > 0`). |

---

### 3.2 Manajemen Pengguna & Hak Akses (`/api/v1/users/*`)

#### A. Form Tambah & Edit Pengguna (`POST /api/v1/users`, `PATCH /api/v1/users/{id}`)
| Field | Wajib (Create) | Wajib (Edit) | Tipe | Min Length | Max Length | Aturan Validasi Frontend |
| :--- | :---: | :---: | :--- | :---: | :---: | :--- |
| `username` | Ya | *(Read-only)* | `string` | `3` | `64` | Wajib cocok `USERNAME_REGEX`; unik *case-insensitive* (`admin` == `ADMIN`). Tidak dapat diubah saat edit. |
| `email` | Ya | Opsional | `string` | `3` | `255` | Wajib cocok `EMAIL_REGEX`; unik *case-insensitive*. |
| `password` | Ya | Opsional | `string` | `8` | `255` | Minimal 8 karakter, tidak boleh hanya spasi. Saat edit, kosongkan jika tidak ingin mengganti password. |
| `full_name` | Ya | Opsional | `string` | `1` | `150` | Wajib diisi setelah `.trim()`. |
| `role_id` | Ya | Opsional | `number` | - | - | Integer positif (`> 0`); harus dipilih dari daftar `GET /api/v1/users/roles`. |
| `is_active` | Opsional (`true`) | Opsional | `boolean` | - | - | **Aturan Self-Lockout:** Jika pengguna mengedit akunnya sendiri (`user.id === currentUser.id`), nonaktifkan input `is_active` dan `role_id` (pengguna tidak boleh menonaktifkan atau mengubah role akunnya sendiri). |
| `warehouse_ids` | Opsional (`[]`) | Via `PUT /{id}/warehouses` | `number[]` | - | - | Daftar ID gudang aktif (`> 0`), otomatis dideduplikasi. |

#### B. Form Pengaturan Permission Role (`PUT /api/v1/users/roles/{role_id}/permissions`)
- **Aturan Self-Lockout Super Admin:** Role `Super Admin` **wajib selalu** memiliki permission `user:manage`. Di UI, kunci (*disable* & centang permanen) checkbox `user:manage` pada role `Super Admin`.

---

### 3.3 Manajemen Menu Navigasi (`/api/v1/menus/*`)

#### Form Tambah & Edit Menu (`POST /api/v1/menus`, `PATCH /api/v1/menus/{id}`)
| Field | Wajib (Create) | Tipe | Min | Max | Aturan Validasi Frontend |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `code` | Ya | `string` | `1` | `50` | Wajib cocok `CODE_REGEX`; unik *case-insensitive*. |
| `name` | Ya | `string` | `1` | `100` | Wajib diisi setelah `.trim()`. |
| `path` | Ya | `string` | `1` | `150` | Wajib diawali `'/'` (contoh: `/master/items`). |
| `icon` | Tidak | `string \| null` | - | `50` | Bila diisi, wajib cocok `ICON_REGEX` (*kebab-case*, contoh: `package-check`). |
| `parent_id` | Tidak | `number \| null` | `> 0` | - | Hanya boleh memilih menu tingkat 1 (menu induk yang memiliki `parent_id === null` dan `is_active === true`). **Maksimal kedalaman hierarki adalah 2 tingkat** (Group → Item). Menu yang sudah punya anak tidak boleh diberi `parent_id`. |
| `sort_order` | Tidak (`0`) | `number` | `0` | `10000` | Bilangan bulat `0` s.d. `10000`. |
| `permission_id` | Tidak | `number \| null` | `> 0` | - | Dipilih dari daftar `GET /api/v1/users/permissions`. |
| `is_active` | Tidak (`true`) | `boolean` | - | - | Menu induk yang masih memiliki submenu aktif tidak dapat dinonaktifkan (`409 ENTITY_IN_USE`). |

---

### 3.4 Master Data (`/api/v1/categories`, `/uoms`, `/suppliers`, `/items`)

#### A. Kategori Barang (`POST /api/v1/categories`, `PATCH /api/v1/categories/{id}`)
| Field | Wajib | Tipe | Min Length | Max Length (`maxLength` UI) | Aturan Validasi Frontend |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `name` | Ya | `string` | `1` | **`120`** | Wajib diisi setelah `.trim()`; unik *case-insensitive*. **Pastikan `maxLength={120}` pada `<input>` sama dengan validasi submit.** |
| `description` | Tidak | `string \| null` | - | **`1000`** | Maksimal 1.000 karakter (`maxLength={1000}`). |
| `is_active` | Tidak (`true`) | `boolean` | - | - | Tidak bisa dinonaktifkan bila masih dipakai oleh barang (`items`) yang aktif (`409 ENTITY_IN_USE`). |

#### B. Satuan Ukur / UoM (`POST /api/v1/uoms`, `PATCH /api/v1/uoms/{id}`)
| Field | Wajib | Tipe | Min Length | Max Length (`maxLength` UI) | Aturan Validasi Frontend |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `code` | Ya | `string` | `1` | **`20`** | Wajib cocok `CODE_REGEX`; unik *case-insensitive*. **Pastikan `maxLength={20}` pada `<input>`.** |
| `name` | Ya | `string` | `1` | **`60`** | Wajib diisi setelah `.trim()`. **Pastikan `maxLength={60}` pada `<input>`.** |
| `allow_decimal` | Tidak (`false`) | `boolean` | - | - | Jika UoM sudah dipakai oleh barang dan saat ini `allow_decimal = true`, tidak dapat diubah menjadi `false` (`409 ENTITY_IN_USE`). |
| `is_active` | Tidak (`true`) | `boolean` | - | - | Tidak bisa dinonaktifkan bila masih dipakai oleh barang aktif (`409 ENTITY_IN_USE`). |

#### C. Pemasok / Supplier (`POST /api/v1/suppliers`, `PATCH /api/v1/suppliers/{id}`)
| Field | Wajib | Tipe | Min Length | Max Length (`maxLength` UI) | Aturan Validasi Frontend |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `code` | Ya | `string` | `1` | **`50`** | Wajib cocok `CODE_REGEX`; unik *case-insensitive*. |
| `name` | Ya | `string` | `1` | **`150`** | Wajib diisi setelah `.trim()`. |
| `contact_person` | Tidak | `string \| null` | - | **`120`** | Maksimal 120 karakter. |
| `phone` | Tidak | `string \| null` | `6` | **`30`** | Bila diisi (setelah `.trim()`), wajib cocok `PHONE_REGEX` (`/^[0-9+() -]{6,30}$/`) dan mengandung minimal 6 digit angka. |
| `email` | Tidak | `string \| null` | - | **`255`** | Bila diisi (setelah `.trim()`), wajib cocok `EMAIL_REGEX`. |
| `address` | Tidak | `string \| null` | - | **`1000`** | Maksimal 1.000 karakter (`maxLength={1000}`). |
| `is_active` | Tidak (`true`) | `boolean` | - | - | Tidak bisa dinonaktifkan bila masih memiliki PO berstatus `DRAFT`, `ISSUED`, atau `PARTIALLY_RECEIVED` (`409 ENTITY_IN_USE`). |

#### D. Barang / SKU (`POST /api/v1/items`, `PATCH /api/v1/items/{id}`)
| Field | Wajib | Tipe | Min Length | Max Length (`maxLength` UI) | Aturan Validasi Frontend |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `sku` | Ya | `string` | `1` | **`64`** | Wajib cocok `CODE_REGEX`; unik *case-insensitive*. **Imutabilitas:** Setelah barang dipakai pada transaksi (PO, GR, Transfer, Opname, atau Ledger), `sku` tidak dapat diubah (`409 ENTITY_IN_USE`). |
| `name` | Ya | `string` | `1` | **`200`** | Wajib diisi setelah `.trim()`. |
| `description` | Tidak | `string \| null` | - | **`1000`** | Maksimal 1.000 karakter (`maxLength={1000}`). |
| `category_id` | Ya | `number` | `> 0` | - | Wajib dipilih dari kategori aktif (`is_active = true`) dari server. |
| `uom_id` | Ya | `number` | `> 0` | - | Wajib dipilih dari UoM aktif (`is_active = true`) dari server. **Imutabilitas:** Tidak dapat diubah setelah barang dipakai pada transaksi (`409 ENTITY_IN_USE`). |
| `is_active` | Tidak (`true`) | `boolean` | - | - | Tidak bisa dinonaktifkan bila total `qty_on_hand != 0` atau masih tercantum pada dokumen aktif yang belum final (`409 ENTITY_IN_USE`). |

---

### 3.5 Gudang & Lokasi Penyimpanan (`/api/v1/warehouses`, `/locations`)

#### A. Gudang / Warehouse (`POST /api/v1/warehouses`, `PATCH /api/v1/warehouses/{id}`)
| Field | Wajib | Tipe | Min Length | Max Length (`maxLength` UI) | Aturan Validasi Frontend |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `code` | Ya | `string` | `1` | **`50`** | Wajib cocok `CODE_REGEX`; unik *case-insensitive*. |
| `name` | Ya | `string` | `1` | **`150`** | Wajib diisi setelah `.trim()`. |
| `address` | Tidak | `string \| null` | - | **`1000`** | Maksimal 1.000 karakter (`maxLength={1000}`). |
| `allow_negative_stock` | Tidak (`false`) | `boolean` | - | - | Hanya dapat dikelola oleh pengguna berizin `warehouse:manage` (Super Admin). |
| `is_active` | Tidak (`true`) | `boolean` | - | - | Tidak bisa dinonaktifkan bila masih ada saldo `!= 0` atau dokumen belum final di gudang tersebut (`409 ENTITY_IN_USE`). |

#### B. Lokasi Penyimpanan / Storage Location (`POST /api/v1/locations`, `POST /api/v1/warehouses/{id}/locations`, `PATCH /api/v1/locations/{id}`)
| Field | Wajib | Tipe | Min Length | Max Length (`maxLength` UI) | Aturan Validasi Frontend |
| :--- | :---: | :--- | :---: | :---: | :--- |
| `warehouse_id` | Ya (Create) | `number` | `> 0` | - | Gudang aktif; pengguna wajib ditugaskan ke gudang tersebut (`403 WAREHOUSE_NOT_ASSIGNED`). Tidak dapat diubah setelah lokasi dibuat. |
| `code` | Ya | `string` | `1` | **`50`** | Wajib cocok `CODE_REGEX`; unik *case-insensitive* di dalam gudang yang sama (`(warehouse_id, LOWER(code))`). |
| `name` | Ya | `string` | `1` | **`120`** | Wajib diisi setelah `.trim()`. |
| `is_active` | Tidak (`true`) | `boolean` | - | - | Tidak bisa dinonaktifkan bila saldo lokasi `!= 0` atau sedang dipakai dokumen belum final (`409 ENTITY_IN_USE`). |

---

### 3.6 Purchase Order / PO (`/api/v1/purchase-orders`)

#### A. Header & Baris PO (`POST /api/v1/purchase-orders`, `PATCH /api/v1/purchase-orders/{id}`)
| Field | Wajib | Tipe | Batas / Format | Aturan Validasi Frontend |
| :--- | :---: | :--- | :--- | :--- |
| `supplier_id` | Ya | `number` | `> 0` | Pemasok harus berstatus `is_active = true` (`422 INACTIVE_REFERENCE`). |
| `warehouse_id` | Ya | `number` | `> 0` | Gudang harus berstatus `is_active = true` (`422 INACTIVE_REFERENCE`). |
| `order_date` | Ya | `string (YYYY-MM-DD)` | Format tanggal ISO | Tanggal pesanan PO. |
| `notes` | Tidak | `string \| null` | `maxLength = 1000` | Catatan header PO. |
| `lines` | Tidak saat `DRAFT`, **Wajib minimal 1 baris saat `issue`** | `array` | Unik per `item_id` | **Satu barang (`item_id`) hanya boleh muncul satu kali dalam satu PO.** |
| `lines[].item_id` | Ya | `number` | `> 0` | Barang harus aktif (`is_active = true`) dan tidak boleh duplikat di PO yang sama. |
| `lines[].qty_ordered` | Ya | `string (Decimal)` | `0 < qty <= 99999999999999.9999` | Wajib `> 0`, maks 4 angka desimal. Bila `item.allow_decimal === false`, wajib bilangan bulat. |
| `lines[].notes` | Tidak | `string \| null` | `maxLength = 500` | Catatan per baris PO. |

#### B. Aksi Status PO
- **Edit (`PATCH /{id}`):** Hanya diizinkan saat status `DRAFT`.
- **Terbitkan (`POST /{id}/issue`):** Hanya dari `DRAFT`, wajib memiliki minimal 1 baris barang (`lines.length >= 1`), semua referensi aktif.
- **Batalkan (`POST /{id}/cancel`):** Hanya dari `DRAFT` atau `ISSUED`, dan **belum memiliki GR berstatus `DRAFT` maupun `POSTED`**.
- **Tutup Paksa (`POST /{id}/close`):** Hanya dari `ISSUED` atau `PARTIALLY_RECEIVED`, tidak boleh ada GR berstatus `DRAFT`, dan wajib mengisi `closed_reason` (`minLength = 1`, `maxLength = 500`, tidak boleh hanya spasi).

---

### 3.7 Goods Receipt / GR (`/api/v1/goods-receipts`)

#### A. Header & Baris GR (`POST /api/v1/goods-receipts`, `PATCH /api/v1/goods-receipts/{id}`)
| Field | Wajib | Tipe | Batas / Format | Aturan Validasi Frontend |
| :--- | :---: | :--- | :--- | :--- |
| `po_id` | Ya (Create) | `number` | `> 0` | PO harus berstatus `ISSUED` atau `PARTIALLY_RECEIVED` (`409 INVALID_STATE_TRANSITION`). Gudang PO harus termasuk gudang penugasan pengguna (`403 WAREHOUSE_NOT_ASSIGNED`). |
| `received_date` | Ya | `string (YYYY-MM-DD)` | **`received_date >= po.order_date`** | **Tanggal penerimaan tidak boleh lebih awal dari `order_date` pada PO terkait (`422 VALIDATION_ERROR`).** |
| `notes` | Tidak | `string \| null` | `maxLength = 1000` | Catatan header GR. |
| `lines` | Tidak saat `DRAFT`, **Wajib minimal 1 baris saat `post`** | `array` | Unik per `(po_line_id, location_id)` | Kombinasi `(po_line_id, location_id)` tidak boleh duplikat di dalam satu GR. |
| `lines[].po_line_id` | Ya | `number` | `> 0` | Harus merupakan baris milik `po_id` yang dipilih. |
| `lines[].location_id` | Ya | `number` | `> 0` | Lokasi harus aktif, milik gudang tujuan PO (`422 INVALID_LOCATION`), dan tidak sedang dibekukan oleh Stock Opname (`409 LOCATION_FROZEN`). |
| `lines[].qty_received` | Ya | `string (Decimal)` | `0 < qty <= sisa pesanan PO` | Wajib `> 0`, maks 4 desimal, bulat bila `allow_decimal = false`. **Aturan Anti Over-Receipt:** Total `qty_received` untuk suatu `po_line_id` pada GR ini tidak boleh melebihi `po_line.qty_ordered - po_line.qty_received` (`409 OVER_RECEIPT`). |
| `lines[].notes` | Tidak | `string \| null` | `maxLength = 500` | Catatan per baris GR. |

---

### 3.8 Stock Transfer (`/api/v1/stock-transfers`)

#### A. Pembuatan & Revisi Transfer (`POST /api/v1/stock-transfers`, `PATCH /api/v1/stock-transfers/{id}`)
| Field | Wajib | Tipe | Batas / Format | Aturan Validasi Frontend |
| :--- | :---: | :--- | :--- | :--- |
| `source_warehouse_id` | Ya | `number` | `> 0` | Gudang asal aktif; pengguna wajib ditugaskan ke gudang asal (`403 WAREHOUSE_NOT_ASSIGNED`). |
| `source_location_id` | Ya | `number` | `> 0` | Lokasi aktif dan wajib milik `source_warehouse_id` (`422 INVALID_LOCATION`). |
| `destination_warehouse_id` | Ya | `number` | `> 0` | Gudang tujuan aktif. |
| `destination_location_id` | Ya | `number` | `> 0` | Lokasi aktif dan wajib milik `destination_warehouse_id` (`422 INVALID_LOCATION`). **Pasangan `(source_warehouse_id, source_location_id)` tidak boleh sama dengan `(destination_warehouse_id, destination_location_id)` (`422 VALIDATION_ERROR`).** |
| `notes` | Tidak | `string \| null` | `maxLength = 1000` | Catatan header Transfer. |
| `lines` | Tidak saat `DRAFT`, **Wajib minimal 1 baris saat `approve`** | `array` | Unik per `item_id` | Satu barang (`item_id`) hanya boleh muncul satu kali dalam satu dokumen Transfer. |
| `lines[].item_id` | Ya | `number` | `> 0` | Barang harus aktif. |
| `lines[].qty` | Ya | `string (Decimal)` | `0 < qty <= 99999999999999.9999` | Wajib `> 0`, maks 4 desimal, bulat bila `allow_decimal = false`. |

#### B. Penerimaan Transfer (`POST /api/v1/stock-transfers/{id}/receive`)
- Hanya dapat dilakukan saat status `SHIPPED` oleh pengguna yang ditugaskan di **gudang tujuan** (`destination_warehouse_id`).
- Payload `lines` wajib mencakup **seluruh baris** pada dokumen Transfer (tidak boleh sebagian baris saja dan tidak boleh duplikat `line_id`):

| Field | Wajib | Tipe | Batas / Format | Aturan Validasi Frontend |
| :--- | :---: | :--- | :--- | :--- |
| `lines[].line_id` | Ya | `number` | `> 0` | ID baris Transfer (`stock_transfer_lines.id`). |
| `lines[].qty_received` | Ya | `string (Decimal)` | **`0 <= qty_received <= qty`** | Boleh `0`, tidak boleh negatif, dan **tidak boleh melebihi `qty` yang dikirim** (`409 TRANSFER_QTY_EXCEEDS_SHIPPED`). Wajib bilangan bulat bila `allow_decimal = false`. |
| `lines[].variance_reason` | **Wajib bila `qty_received < qty`** | `string \| null` | `minLength = 1`, `maxLength = 500` | **Jika `qty_received < qty`, `variance_reason` wajib diisi (tidak boleh kosong/spasi) (`422 VALIDATION_ERROR`).** |

---

### 3.9 Stock Opname (`/api/v1/stock-opnames`)

#### A. Pembuatan & Revisi Sesi Opname (`POST /api/v1/stock-opnames`, `PATCH /api/v1/stock-opnames/{id}`)
| Field | Wajib | Tipe | Batas / Format | Aturan Validasi Frontend |
| :--- | :---: | :--- | :--- | :--- |
| `warehouse_id` | Ya (Create) | `number` | `> 0` | Gudang aktif; pengguna wajib ditugaskan ke gudang tersebut. |
| `location_id` | Tidak (`null` = seluruh gudang) | `number \| null` | `> 0` | Bila diisi, lokasi harus aktif dan milik `warehouse_id` (`422 INVALID_LOCATION`). |
| `notes` | Tidak | `string \| null` | `maxLength = 1000` | Catatan header Opname. |

#### B. Input Hasil Hitung Fisik (`POST /api/v1/stock-opnames/{id}/count`)
- Hanya saat status `IN_PROGRESS`. Setiap item di `lines` harus memenuhi salah satu mode:
  1. **Update baris snapshot yang sudah ada:** isi `line_id` (`> 0`).
  2. **Tambah temuan barang baru di lokasi:** isi `location_id` (`> 0`) dan `item_id` (`> 0`). Jika sesi Opname spesifik pada satu lokasi (`opname.location_id !== null`), maka `location_id` wajib sama dengan `opname.location_id`.

| Field | Wajib | Tipe | Batas / Format | Aturan Validasi Frontend |
| :--- | :---: | :--- | :--- | :--- |
| `lines[].qty_physical` | Ya | `string (Decimal)` | **`0 <= qty <= 99999999999999.9999`** | **Boleh `0`, tidak boleh negatif (`>= 0`)**, maks 4 desimal, wajib bilangan bulat bila `allow_decimal = false`. |
| `lines[].notes` | Tidak | `string \| null` | `maxLength = 500` | Catatan baris hitung fisik. |

#### C. Submit, Approve, & Reject Stock Opname
- **Submit (`POST /{id}/submit`):** Hanya dari `IN_PROGRESS`. **Seluruh baris wajib sudah memiliki `qty_physical !== null`** (tidak boleh ada baris yang belum dihitung) dan minimal harus ada 1 baris pada sesi Opname.
- **Reject (`POST /{id}/reject`):** Hanya dari `WAITING_APPROVAL` kembali ke `IN_PROGRESS`. Wajib mengisi `rejection_reason` (`minLength = 1`, `maxLength = 500`, tidak boleh hanya spasi).
- **Approve (`POST /{id}/approve`):** Hanya dari `WAITING_APPROVAL` oleh `Warehouse Manager` / `Super Admin` (`opname:approve`). Bila ada selisih negatif yang menyebabkan stok menjadi `< 0` pada gudang dengan `allow_negative_stock = false`, sistem menolak dengan `409 INSUFFICIENT_STOCK`.

---

## 4. Parameter Query Pencarian, Filter, & Paginasi (`GET` List Endpoints)

Seluruh endpoint daftar (`GET /api/v1/*`) menerapkan aturan parameter query berikut:

| Query Param | Default | Batas / Format | Perilaku & Validasi |
| :--- | :---: | :--- | :--- |
| `limit` | `50` | `1 <= limit <= 200` | Nilai `<= 0` dinormalisasi ke `50`; nilai `> 200` dibatasi ke `200`. |
| `offset` | `0` | `offset >= 0` | Nilai `< 0` dinormalisasi ke `0`. |
| `search` | `null` | **`maxLength = 100`** | **Maksimal 100 karakter (`> 100` ditolak `422 VALIDATION_ERROR`).** |
| `date_from` & `date_to` | `null` | ISO Date / Datetime | **Jika keduanya diisi, wajib `date_from <= date_to` (`422 VALIDATION_ERROR`).** |
| `sort_by` | Per modul | Sesuai *whitelist* kolom | Hanya menerima nama kolom yang diizinkan di modul terkait; di luar *whitelist* ditolak `422 VALIDATION_ERROR`. |
| `sort_dir` | `asc` / `desc` | `'asc'` atau `'desc'` | Hanya menerima `'asc'` atau `'desc'` (*case-insensitive*). |
| **Semua Filter Opsional** | `null` | String kosong `""` → `null` | Backend otomatis menormalisasi query string kosong (`?date_from=&date_to=&status=&warehouse_id=`) menjadi `null`, namun tetap direkomendasikan di Frontend untuk tidak mengirim parameter yang bernilai kosong. |

---

## 5. Pemetaan Kode Error Backend untuk Ditampilkan di Frontend

Setiap respons gagal dari Backend selalu berbentuk:
```json
{
  "error": {
    "code": "KODE_ERROR",
    "message": "Pesan penjelasan dalam bahasa Indonesia.",
    "details": {}
  }
}
```

Pastikan interceptor HTTP / handler form di Frontend menangani kode berikut secara konsisten:

| HTTP Status | `error.code` | Penanganan yang Direkomendasikan di UI |
| :---: | :--- | :--- |
| `401` | `AUTH_INVALID_CREDENTIALS` | Tampilkan pesan kesalahan pada form login / form ganti password. |
| `401` | `AUTH_TOKEN_EXPIRED` / `AUTH_TOKEN_INVALID` | Lakukan *silent refresh* ke `POST /api/v1/auth/refresh`; bila gagal, bersihkan sesi dan arahkan ke halaman Login. |
| `403` | `PERMISSION_DENIED` | Sembunyikan/nonaktifkan tombol aksi yang tidak sesuai permission pengguna (`actor.permissions`), dan tampilkan toast *"Anda tidak memiliki izin untuk aksi ini."* |
| `403` | `WAREHOUSE_NOT_ASSIGNED` | Filter pilihan gudang di form transaksi hanya pada gudang yang ditugaskan (`actor.warehouse_ids`), kecuali `Super Admin`. |
| `404` | `NOT_FOUND` | Tampilkan state data tidak ditemukan atau arahkan kembali ke halaman daftar. |
| `409` | `DUPLICATE` | Tandai field unik (`code`, `sku`, `username`, `email`, `name`) pada form dengan pesan `error.message` (contoh: *"Barang dengan SKU 'ELK-001' sudah terdaftar."*). |
| `409` | `INVALID_STATE_TRANSITION` | Muat ulang (*refetch*) detail dokumen karena status dokumen telah berubah, dan tampilkan `error.message`. |
| `409` | `INSUFFICIENT_STOCK` | Tampilkan informasi stok tersedia vs diminta dari `error.details` (`qty_available`, `qty_requested`). |
| `409` | `OVER_RECEIPT` | Tampilkan sisa pesanan PO yang masih dapat diterima dari `error.details` (`qty_remaining`, `qty_requested`). |
| `409` | `TRANSFER_QTY_EXCEEDS_SHIPPED` | Tampilkan batas kuantitas kirim (`qty_shipped`) pada baris penerimaan Transfer. |
| `409` | `LOCATION_FROZEN` | Beri peringatan bahwa lokasi sedang dibekukan oleh sesi Stock Opname aktif (`error.details.opname_number`). |
| `409` | `ENTITY_IN_USE` | Beri peringatan bahwa master data / SKU / UoM tidak dapat dinonaktifkan atau diubah karena sedang digunakan pada stok/transaksi aktif. |
| `422` | `INACTIVE_REFERENCE` | Muat ulang dropdown referensi agar pilihan yang sudah dinonaktifkan tidak lagi muncul. |
| `422` | `INVALID_LOCATION` | Reset dropdown lokasi penyimpanan agar hanya menampilkan lokasi milik gudang yang dipilih. |
| `422` | `VALIDATION_ERROR` | Tampilkan `error.message` (dan petakan `error.details.field` atau `error.details.errors` ke field form terkait). |
| `429` | `AUTH_TOO_MANY_ATTEMPTS` | Nonaktifkan tombol login sementara dan tampilkan informasi waktu buka kunci akun (`error.details.locked_until`). |

