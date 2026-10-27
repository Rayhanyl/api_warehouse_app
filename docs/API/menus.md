# Menu Navigasi Dinamis

## 1. Informasi Umum

| Informasi | Keterangan |
| --- | --- |
| Modul | Menu navigasi dinamis |
| Status | Diimplementasikan dan diuji melalui AC-14 |
| Tujuan | Menyediakan struktur navigasi frontend dari database dan menyaringnya berdasarkan permission pengguna aktif. |
| Dependensi | JWT/authentication, RBAC (`permissions`), `menus`, dan `audit_logs`. |
| Sumber utama | `app/api/routes/menus.py`, `app/schemas/menu.py`, `app/services/menu_service.py`, `app/repositories/menu_repo.py`, dan migrasi `009_create_menu_tables.sql`. |

Menu hanya menyediakan metadata navigasi seperti label, path, ikon, urutan, parent, dan permission yang diperlukan. Endpoint backend tetap memeriksa permission masing-masing; menyembunyikan menu di frontend bukan kontrol otorisasi.

## 2. Autentikasi dan Otorisasi

Semua endpoint menu memerlukan access token Bearer yang valid. `GET /api/v1/menus/my-menu` hanya memerlukan pengguna terautentikasi. Endpoint administrasi katalog menu memerlukan permission `user:manage` (diberikan kepada Super Admin sesuai Matriks Permission PRD).

Permission dan status aktif pengguna dibaca dari database pada setiap request. Menu yang mempunyai `permission_id` hanya disertakan pada pohon pengguna bila kode permission tersebut terdapat pada permission aktif pengguna.

## 3. Ringkasan Endpoint

| Method | Endpoint | Fungsi | Auth | Permission |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/menus/my-menu` | Mengambil pohon menu aktif yang terlihat oleh pengguna saat ini. | Bearer | Tidak ada selain autentikasi |
| GET | `/api/v1/menus` | Mencari katalog menu dengan pagination dan filter. | Bearer | `user:manage` |
| POST | `/api/v1/menus` | Membuat menu. | Bearer | `user:manage` |
| GET | `/api/v1/menus/{menu_id}` | Mengambil detail satu menu. | Bearer | `user:manage` |
| PATCH | `/api/v1/menus/{menu_id}` | Memperbarui atau menonaktifkan menu. | Bearer | `user:manage` |

Tidak ada endpoint hard delete. Gunakan `is_active: false` untuk menonaktifkan menu.

## 4. Detail Endpoint

### 4.1 Mengambil Pohon Menu Pengguna

- **Method dan URL:** `GET /api/v1/menus/my-menu`
- **Autentikasi:** Bearer token; tidak memerlukan permission khusus.
- **Parameter:** Tidak ada path parameter, query parameter, atau request body.
- **Respons berhasil:** `200 OK`, array menu root dengan `children` bertingkat.

```bash
curl -X GET "http://localhost:8000/api/v1/menus/my-menu" \
  -H "Authorization: Bearer <access_token>"
```

```json
[
  {
    "id": 1,
    "code": "dashboard",
    "name": "Dashboard",
    "path": "/dashboard",
    "icon": "layout-dashboard",
    "parent_id": null,
    "sort_order": 10,
    "permission_code": null,
    "children": []
  },
  {
    "id": 2,
    "code": "master",
    "name": "Master Data",
    "path": "/master",
    "icon": "database",
    "parent_id": null,
    "sort_order": 20,
    "permission_code": null,
    "children": [
      {
        "id": 10,
        "code": "master_items",
        "name": "Barang (SKU)",
        "path": "/master/items",
        "icon": "package",
        "parent_id": 2,
        "sort_order": 40,
        "permission_code": "master:read",
        "children": []
      }
    ]
  }
]
```

Aturan pohon aktual:

1. Hanya baris `is_active = true` yang diproses.
2. Menu dengan permission hanya dikembalikan jika pengguna memilikinya.
3. Menu induk tanpa permission hanya dikembalikan jika setidaknya satu anak yang terlihat.
4. Menu daun tanpa permission (contohnya Dashboard) terlihat oleh semua pengguna terautentikasi.
5. Urutan setiap tingkat adalah `sort_order ASC`, lalu `id ASC`.

Kemungkinan error: `401 AUTH_TOKEN_INVALID` bila token tidak tersedia/tidak valid.

### 4.2 Membaca Katalog Menu

- **Method dan URL:** `GET /api/v1/menus`
- **Autentikasi dan permission:** Bearer token dan `user:manage`.
- **Query parameter:**

| Parameter | Tipe | Default | Keterangan |
| --- | --- | --- | --- |
| `limit` | integer | 50 | Jumlah maksimum hasil per halaman; rentang 1–200. |
| `offset` | integer | 0 | Posisi awal hasil; tidak boleh negatif. |
| `is_active` | boolean | tidak diterapkan | Filter status aktif. |
| `parent_id` | integer | tidak diterapkan | Filter berdasarkan ID parent. Nilai null tidak menjadi filter root. |
| `search` | string | tidak diterapkan | Pencarian case-insensitive pada `code`, `name`, atau `path`. |
| `sort_by` | string | `sort_order` | Whitelist: `id`, `code`, `name`, `sort_order`, `created_at`. |
| `sort_dir` | string | `ASC` | Arah urut `ASC` atau `DESC`; `id ASC` menjadi pengurut kedua. |

```bash
curl -G "http://localhost:8000/api/v1/menus" \
  -H "Authorization: Bearer <access_token>" \
  --data-urlencode "is_active=true" \
  --data-urlencode "search=master" \
  --data-urlencode "sort_by=sort_order" \
  --data-urlencode "sort_dir=ASC" \
  --data-urlencode "limit=50" \
  --data-urlencode "offset=0"
```

Respons berhasil `200 OK` mengikuti format pagination standar. Setiap elemen `items` memiliki bentuk objek menu pada bagian 5.

```json
{
  "items": [
    {
      "id": 10,
      "code": "master_items",
      "name": "Barang (SKU)",
      "path": "/master/items",
      "icon": "package",
      "parent_id": 2,
      "parent_code": "master",
      "parent_name": "Master Data",
      "sort_order": 40,
      "permission_id": 5,
      "permission_code": "master:read",
      "is_active": true,
      "created_by": null,
      "created_at": "2026-10-27T10:00:00Z",
      "updated_at": "2026-10-27T10:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

Kemungkinan error: `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, dan `422 VALIDATION_ERROR` untuk batas pagination atau kolom/arah sorting yang tidak valid.

### 4.3 Membuat Menu

- **Method dan URL:** `POST /api/v1/menus`
- **Autentikasi dan permission:** Bearer token dan `user:manage`.
- **Respons berhasil:** `201 Created`, objek menu yang dibuat.
- **Request body:**

| Field | Tipe | Wajib | Validasi/default |
| --- | --- | --- | --- |
| `code` | string | Ya | 1–50 karakter; setelah trim tidak boleh kosong; harus unik. |
| `name` | string | Ya | 1–100 karakter; setelah trim tidak boleh kosong. |
| `path` | string | Ya | 1–150 karakter dan harus diawali `/`. |
| `icon` | string atau null | Tidak | Maksimum 50 karakter; kosong dinormalisasi menjadi null. |
| `parent_id` | integer atau null | Tidak | Parent harus ada dan aktif. Default null (menu root). |
| `sort_order` | integer | Tidak | Default 0. |
| `permission_id` | integer atau null | Tidak | Harus merujuk permission yang ada. Default null. |
| `is_active` | boolean | Tidak | Default true. |

```bash
curl -X POST "http://localhost:8000/api/v1/menus" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "inventory_reports",
    "name": "Laporan Stok",
    "path": "/stock/reports",
    "icon": "chart-no-axes-column",
    "parent_id": 2,
    "sort_order": 50,
    "permission_id": 22,
    "is_active": true
  }'
```

Respons berhasil `201 Created` berupa objek `MenuOut` yang sama bentuknya dengan response detail pada bagian 5.

Kemungkinan error: `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `404 NOT_FOUND` untuk parent/permission yang tidak ditemukan, `422 INACTIVE_REFERENCE` untuk parent tidak aktif, `422 VALIDATION_ERROR` untuk path atau payload tidak valid, dan `409 DUPLICATE` untuk kode menu yang sudah dipakai. Perubahan data dan `MENU_CREATED` pada audit log berada dalam satu transaksi.

### 4.4 Membaca Detail Menu

- **Method dan URL:** `GET /api/v1/menus/{menu_id}`
- **Autentikasi dan permission:** Bearer token dan `user:manage`.
- **Path parameter:** `menu_id` adalah ID menu (integer).
- **Respons berhasil:** `200 OK`, objek menu.

```bash
curl -X GET "http://localhost:8000/api/v1/menus/10" \
  -H "Authorization: Bearer <access_token>"
```

Response mengikuti bentuk `MenuOut` pada bagian 5.

Kemungkinan error: `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `404 NOT_FOUND` jika ID tidak ada, dan `422 VALIDATION_ERROR` jika `menu_id` bukan integer.

### 4.5 Memperbarui atau Menonaktifkan Menu

- **Method dan URL:** `PATCH /api/v1/menus/{menu_id}`
- **Autentikasi dan permission:** Bearer token dan `user:manage`.
- **Path parameter:** `menu_id` adalah ID menu (integer).
- **Request body:** semua field selain `clear_parent` dan `clear_permission` opsional; aturan panjang dan validasi field sama dengan `POST`.

`parent_id` yang tidak dikirim mempertahankan parent saat ini. Kirim `clear_parent: true` untuk menjadikan menu root. `permission_id` yang tidak dikirim mempertahankan permission; kirim `clear_permission: true` untuk membuatnya null. `icon: ""` mengosongkan ikon. Kirim `is_active: false` untuk menonaktifkan menu.

```bash
curl -X PATCH "http://localhost:8000/api/v1/menus/12" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Laporan Persediaan", "clear_permission": true}'
```

Respons berhasil `200 OK` berupa objek menu yang sudah diperbarui dengan bentuk `MenuOut` pada bagian 5.

Kemungkinan error: `401 AUTH_TOKEN_INVALID`, `403 PERMISSION_DENIED`, `404 NOT_FOUND` untuk menu/parent/permission yang tidak ditemukan, `422 INACTIVE_REFERENCE` untuk parent nonaktif, `422 VALIDATION_ERROR` untuk payload invalid atau siklus parent, `409 DUPLICATE` untuk kode yang sudah digunakan, dan `409 ENTITY_IN_USE` bila menu induk masih memiliki anak aktif saat akan dinonaktifkan. Update dan audit log (`MENU_UPDATED` atau `MENU_DEACTIVATED`) berada dalam satu transaksi.

## 5. Bentuk Respons

Objek katalog (`MenuOut`) yang dikembalikan oleh endpoint administrasi berisi:

```json
{
  "id": 12,
  "code": "inventory_reports",
  "name": "Laporan Stok",
  "path": "/stock/reports",
  "icon": "chart-no-axes-column",
  "parent_id": 2,
  "parent_code": "inventory",
  "parent_name": "Stok & Buku Besar",
  "sort_order": 50,
  "permission_id": 22,
  "permission_code": "stock:read",
  "is_active": true,
  "created_by": 1,
  "created_at": "2026-10-27T10:00:00Z",
  "updated_at": "2026-10-27T10:00:00Z"
}
```

Nilai ID dan waktu pada contoh hanya ilustrasi. Response pohon pengguna memakai `MenuTreeOut`: `id`, `code`, `name`, `path`, `icon`, `parent_id`, `sort_order`, `permission_code`, dan `children`.

## 6. Relasi Data dan Seed

Tabel `menus` dibuat di `db/migrations/009_create_menu_tables.sql`. `parent_id` adalah self-FK dengan `ON DELETE RESTRICT`; `permission_id` mengacu ke `permissions` dengan `ON DELETE SET NULL`. Tabel memiliki unique constraint pada `code`, check constraint agar menu tidak menunjuk dirinya sendiri, serta indeks parent, permission, urutan, dan status aktif. Kode aplikasi tidak menyediakan hard delete.

Migrasi mengisi menu awal untuk Dashboard, Master Data, Stok & Buku Besar, Pengadaan & Penerimaan, Operasional Gudang, dan Administrasi & Keamanan beserta submenu modul. Permission pada submenu berasal dari permission RBAC yang sudah tersedia. Seed menggunakan `ON CONFLICT (code) DO NOTHING`.

## 7. Catatan dan Status Verifikasi

- Tes AC-14 berada di `tests/test_menus.py`; ketiga skenario menu dan seluruh suite (21 tes) lulus pada PostgreSQL `wms_test` saat verifikasi dokumentasi ini disusun.
- Endpoint tidak menyediakan hard delete dan tidak mengubah hak akses endpoint bisnis. Permission pada menu hanya menentukan visibilitas navigasi.
- `GET /api/v1/menus/my-menu` tidak memakai pagination; hasil berupa seluruh pohon yang terlihat oleh pengguna.
