# Catatan Permasalahan Admin

Dokumen ini mencatat dua hal yang perlu diperbaiki pada base admin Jejakstok:

1. Sesi pengguna hilang ketika halaman di-hard refresh menggunakan `Ctrl + Shift + R`.
2. Struktur data JSON menu perlu dibuat lebih konsisten agar dapat dirender dengan baik
   pada sidebar terbuka maupun sidebar ciut.

## 1. Logout saat hard refresh

### Gejala

Ketika pengguna sudah login di dashboard kemudian menekan `Ctrl + Shift + R`,
halaman dimuat ulang dan pengguna diarahkan kembali ke halaman login.

Hard refresh tidak seharusnya dianggap sebagai logout. Pengguna hanya meminta
browser memuat ulang seluruh aplikasi dari server.

### Penyebab pada implementasi saat ini

Saat ini token dibagi menjadi dua jenis:

- access token disimpan di memory Zustand;
- refresh token disimpan di `localStorage` dengan key
  `wms.frontend.auth.refresh-token`.

Access token di memory akan hilang setiap kali aplikasi dimuat ulang. Setelah
hard refresh, `ProtectedRoute` harus menjalankan proses berikut:

```text
Muat aplikasi
  -> baca refresh token
  -> POST /api/v1/auth/refresh
  -> simpan access token baru di memory
  -> GET /api/v1/auth/me
  -> tampilkan dashboard
```

Jika proses tersebut gagal, sesi dibersihkan dan pengguna diarahkan ke `/login`.
Kemungkinan penyebabnya:

- refresh token tidak tersedia atau sudah kedaluwarsa;
- request refresh berjalan setelah redirect ke `/login`;
- backend tidak menerima refresh token karena CORS, host, atau konfigurasi cookie;
- frontend menggunakan `localhost`, sedangkan konfigurasi atau backend memakai
  `127.0.0.1`;
- response refresh gagal tetapi error hanya ditampilkan sebagai sesi tidak tersedia;
- state pemulihan sesi belum memiliki status yang membedakan `memuat`, `berhasil`,
  dan `gagal`.

### Kesimpulan sementara: perlu penyesuaian backend dan frontend

Perbaikan frontend saja belum cukup jika backend tidak mempertahankan refresh
session dengan benar. Hard refresh menghapus access token dari memory browser,
sehingga endpoint `POST /api/v1/auth/refresh` menjadi satu-satunya cara untuk
mendapatkan access token baru.

Ada dua area yang harus diperiksa bersamaan:

1. **Backend** harus menerima refresh token yang masih valid, menerbitkan access
   token baru, dan mengembalikan refresh token baru jika menerapkan rotation.
2. **Frontend** harus menunggu hasil refresh sebelum melakukan redirect serta
   tidak menghapus refresh token ketika error hanya disebabkan jaringan atau
   server sementara.

Catatan penting pada implementasi frontend saat ini: ketika tidak ada refresh
token, `refreshSession()` mengembalikan `null`. Alur pemulihan harus tetap
menutup status `checking` pada kondisi tersebut agar aplikasi tidak menunggu
selamanya. Kondisi ini harus dibedakan dari refresh token yang invalid dan dari
server yang tidak dapat dihubungi.

### Kontrak backend autentikasi yang harus dipastikan

#### Login

```text
POST /api/v1/auth/login
Body: { "username": string, "password": string }
```

Response minimal:

```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "expires_in": 900,
  "access_expires_at": "2026-10-27T08:00:00Z"
}
```

#### Refresh

```text
POST /api/v1/auth/refresh
Body: { "refresh_token": "string" }
```

Backend harus:

- menerima token yang belum kedaluwarsa dan belum dicabut;
- memvalidasi signature, subject, token type, dan session identifier;
- mengembalikan `access_token` baru;
- mengembalikan `refresh_token` baru bila rotation digunakan;
- menyimpan atau memperbarui session refresh token secara atomik;
- mengembalikan `401` dengan error code yang stabil untuk token invalid;
- tidak mengembalikan `401` untuk kegagalan koneksi database atau error server;
- mengembalikan `5xx` untuk kegagalan internal agar frontend tidak menganggap
  pengguna harus login ulang.

Jika refresh token rotation digunakan, token lama harus ditandai sudah dipakai
setelah token baru berhasil dibuat. Jangan mencabut seluruh session pengguna
ketika request refresh gagal karena timeout atau database sementara tidak
tersedia.

#### Current user

```text
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

Endpoint ini harus menerima access token yang baru diterbitkan oleh endpoint
refresh dan mengembalikan user aktif beserta permission dan `warehouse_ids`.

#### CORS dan host

Untuk development, backend harus mengizinkan origin frontend yang benar,
misalnya:

```text
http://localhost:5173
```

atau:

```text
http://127.0.0.1:5173
```

Pilih origin yang benar-benar digunakan browser. Jika refresh token dipindahkan
ke HttpOnly cookie, backend juga wajib mengatur:

- `Access-Control-Allow-Credentials: true`;
- `Access-Control-Allow-Origin` tidak boleh `*`;
- atribut cookie `HttpOnly`, `Secure` sesuai environment, dan `SameSite` yang
  sesuai topologi frontend/backend.

### Checklist investigasi backend untuk hard refresh

- [ ] Refresh token yang diterbitkan saat login tersimpan atau dapat diverifikasi.
- [ ] Refresh token belum langsung dicabut setelah endpoint login selesai.
- [ ] Endpoint refresh dapat dipanggil ulang setelah browser di-refresh.
- [ ] Rotation refresh token tidak menghapus token baru secara tidak sengaja.
- [ ] Token invalid menghasilkan `401` dan error code yang konsisten.
- [ ] Error database, timeout, dan exception internal menghasilkan `5xx`.
- [ ] Endpoint `/auth/me` menerima access token hasil refresh.
- [ ] CORS mengizinkan origin frontend yang sedang dipakai.
- [ ] Jika memakai cookie, credentials dan atribut cookie sudah benar.
- [ ] Log backend mencatat alasan refresh gagal tanpa mencatat nilai token.

### Perbaikan yang direkomendasikan

#### A. Gunakan satu host API secara konsisten

Gunakan konfigurasi berikut untuk development:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Frontend, backend, dan aturan CORS harus menggunakan host yang konsisten.
Jangan mencampur `localhost` dan `127.0.0.1` untuk alur autentikasi yang sama.

#### B. Pastikan pemulihan sesi selesai sebelum redirect

`ProtectedRoute` sebaiknya memiliki state eksplisit:

```text
unknown    -> sedang memeriksa sesi
authenticated -> tampilkan halaman admin
unauthenticated -> arahkan ke login
```

Jangan langsung menjalankan `<Navigate to="/login" />` ketika access token belum
tersedia. Tunggu request refresh selesai terlebih dahulu.

#### C. Jangan menghapus refresh token untuk error jaringan sementara

Refresh token hanya boleh dihapus jika backend secara jelas mengembalikan
token tidak valid atau sesi sudah dicabut. Untuk error jaringan, timeout, atau
server sedang mati, tampilkan pesan kesalahan dan sediakan tombol coba lagi.

Contoh klasifikasi:

| Kondisi | Tindakan |
|---|---|
| `401` atau kode token tidak valid | Hapus sesi dan arahkan ke login |
| `5xx` dari backend | Pertahankan refresh token, tampilkan coba lagi |
| Timeout atau jaringan terputus | Pertahankan refresh token, tampilkan coba lagi |
| Refresh berhasil | Simpan token baru dan muat profil pengguna |

#### D. Pertimbangkan refresh token berbasis HttpOnly cookie

Untuk production, pilihan yang lebih aman adalah menyimpan refresh token pada
cookie `HttpOnly`, `Secure`, dan `SameSite` yang sesuai. Dengan pendekatan ini,
JavaScript tidak dapat membaca refresh token secara langsung.

Jika pendekatan ini dipakai, backend dan frontend perlu disesuaikan:

- backend mengatur cookie saat login atau refresh;
- Axios menggunakan `withCredentials: true`;
- CORS mengizinkan credentials;
- logout menghapus cookie dari backend.

Jika masih menggunakan `localStorage` untuk development, jangan pernah
menyimpan access token di `localStorage`.

### Acceptance criteria autentikasi

- [ ] `Ctrl + Shift + R` tidak mengeluarkan pengguna selama refresh token masih valid.
- [ ] Tampilan `Memulihkan sesi...` muncul sebelum keputusan autentikasi dibuat.
- [ ] Refresh token yang valid menghasilkan access token baru.
- [ ] Error jaringan tidak langsung menghapus refresh token.
- [ ] Token invalid atau sesi dicabut tetap mengarahkan pengguna ke login.
- [ ] Logout manual menghapus state memory dan token penyimpanan.
- [ ] Host API dan aturan CORS konsisten pada seluruh environment.
- [ ] Tidak ada refresh token yang dihapus karena error jaringan sementara.
- [ ] Kondisi tidak ada refresh token menyelesaikan status pemulihan dan
  mengarahkan pengguna ke login secara deterministik.

## 2. Perbaikan data JSON menu

### Prinsip utama

Sidebar yang ciut seharusnya mengubah **cara menampilkan** menu, bukan mengubah
data menu dari backend. Satu response menu harus dapat dipakai untuk:

- sidebar terbuka;
- sidebar ciut;
- drawer mobile;
- command palette;
- breadcrumb;
- pintasan dashboard.

Jangan membuat response JSON berbeda hanya untuk sidebar terbuka dan ciut.
Frontend cukup menggunakan `icon` dan nama menu sebagai tooltip ketika sidebar
ciut.

### Struktur JSON yang disarankan

Contoh response `GET /api/v1/menus/my-menu`:

```json
[
  {
    "id": 1,
    "code": "dashboard",
    "name": "Dasbor",
    "short_name": "Dasbor",
    "path": "/dashboard",
    "icon": "layout-dashboard",
    "menu_type": "item",
    "parent_id": null,
    "sort_order": 10,
    "is_active": true,
    "is_visible": true,
    "children": []
  },
  {
    "id": 2,
    "code": "master-data",
    "name": "Master data",
    "short_name": "Master data",
    "path": "/master",
    "icon": "database",
    "menu_type": "group",
    "parent_id": null,
    "sort_order": 20,
    "is_active": true,
    "is_visible": true,
    "children": [
      {
        "id": 3,
        "code": "items",
        "name": "Barang (SKU)",
        "short_name": "Barang",
        "path": "/master/items",
        "icon": "package",
        "menu_type": "item",
        "parent_id": 2,
        "sort_order": 10,
        "is_active": true,
        "is_visible": true,
        "children": []
      }
    ]
  }
]
```

### Arti field

| Field | Wajib | Keterangan |
|---|---:|---|
| `id` | Ya | Identifier unik menu |
| `code` | Ya | Identifier stabil untuk frontend dan permission |
| `name` | Ya | Nama lengkap yang tampil saat sidebar terbuka |
| `short_name` | Disarankan | Nama ringkas untuk tooltip, mobile, atau konteks sempit |
| `path` | Ya | Path React Router; group tanpa halaman dapat memakai path induk atau `null` bila kontrak diubah |
| `icon` | Disarankan | Nama icon dari daftar yang disepakati, bukan komponen atau SVG mentah |
| `menu_type` | Disarankan | `group` untuk induk dan `item` untuk halaman yang dapat dibuka |
| `parent_id` | Ya | Relasi parent-child |
| `sort_order` | Ya | Urutan menu dari backend |
| `is_active` | Ya | Status aktif dari konfigurasi menu |
| `is_visible` | Disarankan | Menandai menu yang boleh dirender |
| `children` | Ya | Array child, gunakan `[]` jika tidak ada |

### Aturan data menu

1. `code` harus unik dan tidak berubah hanya karena label diterjemahkan.
2. `path` harus dimulai dengan `/` dan tidak boleh kosong untuk menu yang bisa
   diklik.
3. Menu induk hanya dirender jika memiliki child yang terlihat atau memang
   merupakan halaman yang dapat dibuka.
4. `sort_order` harus dikirim dari backend agar urutan sidebar konsisten.
5. `icon` harus memakai daftar nama yang disepakati, misalnya
   `layout-dashboard`, `package`, `warehouse`, `truck`, dan `users`.
6. Jangan mengirim nama icon yang terlalu bervariasi seperti `BoxIcon`,
   `box-icon`, dan `box` untuk arti yang sama.
7. Permission tetap ditentukan backend. Frontend tidak boleh menampilkan menu
   hanya berdasarkan nama atau `code`.
8. `children` selalu berupa array agar renderer tidak perlu menangani
   `null` atau bentuk response yang berbeda.
9. Label panjang tidak perlu dipotong oleh backend. Pemotongan, wrapping, dan
   tooltip adalah tanggung jawab komponen sidebar.
10. Menu yang tidak memiliki akses pengguna jangan dikirim dalam response
    `my-menu`.

### Penyesuaian frontend untuk sidebar ciut

Frontend sebaiknya menerapkan aturan berikut:

- sidebar terbuka menggunakan `name`;
- sidebar ciut hanya menampilkan icon;
- `name` atau `short_name` digunakan sebagai `title` dan accessible label;
- menu induk dengan child ditampilkan melalui flyout saat sidebar ciut;
- flyout memiliki lebar tetap yang cukup untuk membaca nama menu;
- menu item tidak menyebabkan lebar halaman bertambah;
- `overflow-x` halaman tetap tersembunyi, sedangkan flyout berada di luar
  container sidebar dengan positioning yang tepat;
- menu aktif tetap ditandai menggunakan `aria-current="page"`.

### Checklist integrasi menu

- [ ] Response menu memiliki struktur tree yang konsisten.
- [ ] Semua menu memiliki `id`, `code`, `name`, `path`, `icon`, dan `children`.
- [ ] Nama icon mengikuti daftar yang disepakati backend dan frontend.
- [ ] Menu induk dan child memiliki `sort_order`.
- [ ] Menu ciut mempunyai tooltip atau accessible label.
- [ ] Flyout menu dapat dibuka dan seluruh child dapat diklik.
- [ ] Menu panjang tidak memperlebar viewport.
- [ ] Command palette menggunakan response menu yang sama.
- [ ] Dashboard hanya menampilkan pintasan dari menu yang diizinkan backend.

### Kontrak menu yang perlu disepakati dengan backend

Endpoint:

```text
GET /api/v1/menus/my-menu
Authorization: Bearer <access_token>
```

Response harus selalu berupa array tree, termasuk ketika pengguna tidak
memiliki menu:

```json
[]
```

Setiap node menu minimal memiliki:

```json
{
  "id": 1,
  "code": "items",
  "name": "Barang (SKU)",
  "path": "/master/items",
  "icon": "package",
  "parent_id": 2,
  "sort_order": 10,
  "permission_code": "item:read",
  "is_active": true,
  "is_visible": true,
  "menu_type": "item",
  "children": []
}
```

Backend dan frontend harus menyepakati hal berikut:

- `children` selalu array, bukan `null`;
- node diurutkan berdasarkan `sort_order` pada setiap level;
- menu tanpa permission tidak dikirim;
- menu inactive tidak dikirim;
- menu yang dikirim oleh endpoint `my-menu` selalu memiliki `is_active: true`;
- menu yang dikirim telah lolos filter permission dan memiliki `is_visible: true`;
- `menu_type` bernilai `group` jika node memiliki child dan `item` jika tidak memiliki child;
- parent tanpa child yang terlihat tidak dikirim, kecuali parent dapat dibuka
  sebagai halaman;
- `path` menu yang dapat diklik selalu diawali `/`;
- `code` stabil dan unik;
- `icon` menggunakan enum nama icon yang sama dengan mapping frontend;
- response tidak mengirim komponen React, SVG mentah, atau nama class CSS;
- perubahan label tidak mengubah `code` atau `path`;
- backend melakukan filter permission, frontend hanya merender response.

### Contoh enum icon yang disarankan

Gunakan daftar kecil dan stabil:

```text
layout-dashboard
database
package
warehouse
truck
clipboard-check
arrow-left-right
users
shield-check
file-text
settings
```

Jika backend saat ini menggunakan nilai seperti `box`, `BoxIcon`, atau
`package-box` secara bergantian, lakukan migrasi data ke satu nilai canonical.
Frontend boleh menyediakan fallback icon, tetapi fallback tidak boleh menjadi
pengganti kontrak data yang konsisten.

## Prioritas pengerjaan

### Prioritas 1 — autentikasi

1. Tambahkan state pemulihan sesi yang eksplisit.
2. Pastikan refresh request selesai sebelum redirect ke login.
3. Bedakan token invalid dari error jaringan.
4. Tambahkan logging terkontrol untuk status refresh di development.
5. Uji hard refresh, refresh token kedaluwarsa, backend mati, dan logout manual.

### Prioritas 2 — kontrak menu backend

1. Samakan daftar field JSON antara backend dan frontend.
2. Tetapkan enum icon dan `menu_type`.
3. Pastikan `children` selalu array.
4. Pastikan `sort_order` dan permission diproses di backend.
5. Uji menu pada sidebar terbuka, sidebar ciut, mobile drawer, dan command palette.

## 3. Catatan Tindak Lanjut Frontend Setelah Perbaikan Backend

Bagian ini adalah daftar pekerjaan frontend yang wajib disesuaikan dengan
perubahan backend yang sudah diterapkan. Perbaikan backend tidak otomatis
memulihkan sesi apabila frontend langsung mengarahkan pengguna ke `/login`
sebelum proses restore session selesai.

### 3.1 Konfigurasi host API dan CORS

Backend development sekarang mengizinkan origin berikut secara eksplisit:

```text
http://localhost:5173
http://127.0.0.1:5173
```

Frontend harus memilih satu host API secara konsisten pada setiap environment.
Contoh:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

atau:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Catatan implementasi:

- Jangan mencampur `localhost` dan `127.0.0.1` tanpa alasan.
- Origin halaman frontend harus termasuk dalam `FRONTEND_ORIGINS` backend.
- Axios harus mengirim `Authorization: Bearer <access_token>` untuk endpoint
  yang memerlukan autentikasi.
- Refresh token dikirim sebagai JSON body, bukan cookie:

```json
{
  "refresh_token": "..."
}
```

- Jangan mengaktifkan `withCredentials` sebagai pengganti header Bearer karena
  backend saat ini menggunakan `allow_credentials: false`.

### 3.2 Restore session setelah hard refresh

Access token memang disimpan di memory dan akan hilang ketika browser
melakukan hard refresh. Frontend wajib memiliki satu proses pemulihan sesi
terpusat dengan state berikut:

```text
checking -> authenticated
checking -> unauthenticated
checking -> unavailable
```

Urutan yang wajib:

```text
1. Aplikasi dimuat.
2. Baca refresh token dari storage adapter/localStorage.
3. Jika tidak ada refresh token, tetapkan unauthenticated.
4. Jika ada, POST /api/v1/auth/refresh.
5. Simpan access token baru di memory/Zustand.
6. Simpan refresh token hasil rotation untuk menggantikan token lama.
7. GET /api/v1/auth/me menggunakan access token baru.
8. Simpan profil dan permission user.
9. Tetapkan authenticated dan render route terlindungi.
```

Ketentuan:

- `ProtectedRoute` tidak boleh melakukan redirect ketika status masih
  `checking`.
- Tampilkan state `Memulihkan sesi...` selama proses berlangsung.
- Hanya satu request restore/refresh yang boleh berjalan pada satu waktu.
- Request API yang menerima `401` dapat mencoba refresh satu kali, lalu
  mengulang request asli satu kali setelah refresh berhasil.
- Hindari loop refresh tanpa batas.
- Setelah refresh berhasil, refresh token lama harus segera diganti dengan
  refresh token baru dari response backend.

### 3.3 Klasifikasi error refresh

Frontend harus membedakan hasil berikut:

| Kondisi backend | Tindakan frontend |
|---|---|
| `200` dari `/auth/refresh` | Simpan pasangan token baru dan lanjutkan restore |
| `401 AUTH_TOKEN_INVALID` | Hapus access/refresh token, reset session, arahkan ke login |
| `403` | Tampilkan akses ditolak; jangan menganggap token otomatis valid |
| `422 VALIDATION_ERROR` | Perbaiki payload; jangan retry otomatis |
| `5xx` | Pertahankan refresh token, tampilkan error dan tombol coba lagi |
| Timeout/network error | Pertahankan refresh token, tampilkan status offline/gagal sementara |

Frontend tidak boleh menghapus refresh token untuk timeout, network error, atau
`5xx`. Penghapusan token hanya dilakukan jika backend secara jelas menyatakan
token tidak valid atau sesi sudah dicabut.

Pesan error backend mengikuti bentuk:

```json
{
  "error": {
    "code": "AUTH_TOKEN_INVALID",
    "message": "Refresh token tidak valid.",
    "details": {}
  }
}
```

Refresh token tidak boleh masuk ke log browser, URL, telemetry, atau pesan
error yang ditampilkan kepada pengguna.

### 3.4 Penyesuaian renderer menu

Backend `GET /api/v1/menus/my-menu` sekarang mengembalikan field tambahan:

- `is_active`
- `is_visible`
- `menu_type`

Frontend harus:

- memperbarui TypeScript type/schema response menu;
- menerima `menu_type: "group" | "item"`;
- menggunakan `menu_type` untuk menentukan apakah node membuka child/flyout;
- menggunakan `children` sebagai array tanpa normalisasi `null`;
- tetap merender hanya response dari backend dan tidak melakukan pemeriksaan
  permission sebagai sumber otorisasi;
- menggunakan `icon` sebagai nama icon Lucide melalui mapping allowlist;
- menggunakan `code` sebagai identifier stabil, bukan `name`;
- menggunakan `path` untuk navigasi React Router;
- menampilkan tooltip/accessibility label ketika sidebar ciut;
- tidak menampilkan parent kosong;
- menandai route aktif dengan `aria-current="page"`.

Contoh type frontend:

```ts
type MenuType = "group" | "item";

type MenuNode = {
  id: number;
  code: string;
  name: string;
  path: string;
  icon: string | null;
  parent_id: number | null;
  sort_order: number;
  permission_code: string | null;
  is_active: boolean;
  is_visible: boolean;
  menu_type: MenuType;
  children: MenuNode[];
};
```

`is_visible` dan `is_active` adalah metadata dari backend untuk kebutuhan
rendering. Keduanya bukan pengganti pemeriksaan permission pada endpoint
bisnis; seluruh endpoint tetap harus menangani `403 PERMISSION_DENIED`.

### 3.5 Test frontend yang wajib ditambahkan

- Restore session berhasil setelah access token memory dihapus dan refresh
  token masih valid.
- Restore session tidak melakukan redirect ketika request refresh masih loading.
- Refresh berhasil menyimpan refresh token hasil rotation.
- `401 AUTH_TOKEN_INVALID` menghapus session dan mengarahkan ke login.
- Timeout/network error mempertahankan refresh token.
- Response `5xx` mempertahankan refresh token dan menyediakan retry.
- Dua request bersamaan memakai satu refresh request/mutex.
- Menu dengan `menu_type: "group"` menampilkan child.
- Menu dengan `menu_type: "item"` melakukan navigasi ke `path`.
- Menu sidebar ciut menampilkan icon dan accessible label.
- Menu parent tanpa child tidak dirender.
- Response `[]` menghasilkan empty state tanpa error.
- Field `is_active`, `is_visible`, dan `menu_type` tervalidasi oleh schema
  frontend.
