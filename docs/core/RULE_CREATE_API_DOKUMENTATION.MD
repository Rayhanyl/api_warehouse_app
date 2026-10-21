Tolong buatkan dokumentasi untuk seluruh service API yang telah dibuat dalam format Markdown (`.md`) dan simpan seluruh file dokumentasi di dalam folder `docs/api/`.

Dokumentasi harus akurat, konsisten, dan berdasarkan implementasi aplikasi yang tersedia. Terapkan seluruh aturan berikut.

## 1. Prioritas Sumber Informasi

Gunakan urutan prioritas sumber informasi berikut sebagai acuan utama saat menyusun dokumentasi:

1. **Implementasi kode aktual** — sumber utama untuk menentukan perilaku API, termasuk route, controller, request validation, resource, service, repository, model, middleware, policy, dan kode terkait lainnya.
2. **Skema database dan migration** — acuan untuk struktur tabel, tipe data, constraint, foreign key, relasi, nullable, default value, dan aturan integritas data.
3. **Test otomatis** — gunakan unit test, feature test, integration test, dan API test untuk memverifikasi perilaku yang diharapkan serta kondisi khusus yang sudah diuji.
4. **Dokumentasi teknis dan bisnis yang sudah tersedia** — gunakan PRD, dokumentasi alur bisnis, spesifikasi API, dan dokumen lain sebagai sumber konteks dan tujuan fitur.
5. **Komentar kode dan catatan developer** — gunakan sebagai informasi pendukung, bukan sebagai pengganti implementasi aktual.
6. **Asumsi atau interpretasi** — jangan digunakan sebagai fakta. Jika informasi tidak dapat diverifikasi dari sumber yang tersedia, tandai sebagai **Perlu Ditinjau**.

### Aturan Penerapan Prioritas

- Jika dokumentasi lama berbeda dengan implementasi kode, dokumentasikan perilaku aktual dan catat perbedaannya jika berdampak pada pemahaman atau penggunaan API.
- Jika PRD atau dokumentasi bisnis berbeda dengan implementasi, jangan langsung menganggap salah satunya sebagai kebenaran mutlak. Dokumentasikan perilaku aktual, jelaskan perbedaannya, dan tandai kebutuhan konfirmasi apabila implementasi belum sesuai dengan kebutuhan bisnis.
- Jika komentar kode tidak sesuai dengan perilaku program, ikuti perilaku aktual yang dapat diverifikasi.
- Jika test berbeda dengan implementasi, jangan menganggap test otomatis selalu benar. Periksa apakah test sudah usang, implementasi mengalami regresi, atau terdapat perubahan kebutuhan.
- Jika beberapa sumber dengan tingkat prioritas yang sama saling bertentangan, lakukan pemeriksaan lebih lanjut dan jangan memilih salah satu tanpa dasar yang jelas.
- Jangan membuat endpoint, parameter, response, permission, relasi, atau aturan bisnis yang tidak ditemukan dalam sumber yang tersedia.
- Bedakan dengan jelas antara **perilaku yang sudah diimplementasikan**, **kebutuhan bisnis yang terdokumentasi**, dan **hal yang masih perlu dikonfirmasi**.
- Jangan mengubah kode aplikasi hanya untuk menyesuaikannya dengan dokumentasi, kecuali perubahan kode memang diminta secara terpisah.

## 2. Standar Format Dokumentasi

Gunakan struktur yang konsisten untuk setiap file dokumentasi API.

### 2.1 Informasi Umum
- Nama modul atau fitur.
- Deskripsi singkat.
- Tujuan dan fungsi API.
- Status implementasi jika dapat diverifikasi.
- Dependensi atau modul terkait.

### 2.2 Penjelasan Fitur
Jelaskan tujuan fitur, masalah yang diselesaikan, cara kerja, alur bisnis, peran pengguna, serta hubungannya dengan modul lain.

### 2.3 Autentikasi dan Otorisasi
Dokumentasikan mekanisme autentikasi, token, header, role, permission, dan pembatasan akses berdasarkan implementasi aktual.

### 2.4 Ringkasan Endpoint

Gunakan tabel dengan format berikut:

| Method | Endpoint | Fungsi | Auth | Permission |
|---|---|---|---|---|
| GET | `/api/example` | Mengambil data | Sesuai kode | Sesuai kode |

Ganti endpoint contoh dengan endpoint aktual dari proyek.

### 2.5 Detail Setiap Endpoint

Gunakan struktur berikut untuk setiap endpoint:

- **Nama endpoint dan deskripsi**
- **HTTP method dan URL**
- **Autentikasi dan permission**
- **Path parameter dan query parameter**
- **Request body**, termasuk tipe data, field wajib atau opsional, dan aturan validasi
- **Contoh request**
- **Contoh response berhasil**
- **Kemungkinan response error**, termasuk status code dan penyebabnya
- **Aturan bisnis**
- **Relasi dan dampak terhadap data lain**
- **Pagination, filtering, sorting**, jika tersedia
- **Catatan implementasi dan batasan**

Pastikan contoh request dan response sesuai dengan implementasi aktual, bukan format generik yang belum tentu digunakan oleh aplikasi.

### 2.6 Relasi dan Ketergantungan
Jelaskan keterkaitan API dengan model, tabel, foreign key, service, repository, modul lain, dan layanan eksternal jika relevan.

### 2.7 Contoh Penggunaan
Sertakan contoh pemanggilan menggunakan cURL, header autentikasi, request body, dan response sesuai kebutuhan endpoint.

### 2.8 Catatan dan Status Verifikasi
Tandai informasi yang belum dapat dipastikan sebagai **Perlu Ditinjau**. Jika ditemukan perbedaan antara kebutuhan bisnis dan implementasi, jelaskan keduanya secara terpisah.

## 3. Indeks Dokumentasi API

Buat file `docs/api/README.md` sebagai indeks utama yang mencakup:

- Gambaran umum API aplikasi.
- Daftar modul atau domain bisnis.
- Deskripsi singkat fungsi setiap modul.
- Ringkasan fitur dan endpoint yang tersedia.
- Tautan relatif menuju file dokumentasi setiap modul.
- Catatan mengenai dokumentasi yang masih perlu ditinjau.

Pastikan setiap file dokumentasi baru, perubahan, atau penghapusan selalu diikuti pembaruan indeks.

## 4. Standar Penamaan dan Struktur File

Gunakan nama file yang konsisten, huruf kecil, dan tanda hubung jika diperlukan.

Contoh struktur:

```text
docs/
└── api/
    ├── README.md
    ├── authentication.md
    ├── books.md
    ├── members.md
    ├── transactions.md
    └── reports.md
```

Struktur tersebut hanya contoh. Sesuaikan dengan modul yang benar-benar tersedia di aplikasi. Gunakan subfolder jika diperlukan untuk mengelompokkan dokumentasi berdasarkan domain bisnis.

## 5. Standar Penulisan

- Gunakan bahasa Indonesia yang profesional, jelas, dan mudah dipahami.
- Gunakan heading Markdown secara berurutan.
- Gunakan tabel untuk informasi terstruktur.
- Gunakan blok kode dengan bahasa yang sesuai, seperti `json`, `bash`, atau `php`.
- Hindari pengulangan yang tidak diperlukan.
- Pisahkan penjelasan fungsi bisnis dari detail teknis API.
- Pertahankan format yang sama pada seluruh file.
- Jangan mencantumkan informasi sensitif, token asli, password, atau kredensial dari konfigurasi proyek.

## 6. Tahapan Pengerjaan

1. Periksa struktur proyek dan inventarisasi seluruh route API.
2. Telusuri controller, request validation, resource, service, repository, model, middleware, policy, migration, dan test terkait.
3. Periksa dokumentasi bisnis dan teknis yang tersedia.
4. Terapkan aturan prioritas sumber informasi untuk menyelesaikan perbedaan antarsumber.
5. Kelompokkan endpoint berdasarkan modul atau domain bisnis.
6. Buat dokumentasi setiap modul menggunakan format standar.
7. Buat atau perbarui `docs/api/README.md`.
8. Verifikasi kembali seluruh detail endpoint, request, response, validasi, permission, dan aturan bisnis.
9. Periksa semua tautan relatif serta kelengkapan dokumentasi.
10. Buat ringkasan hasil pengerjaan, termasuk jumlah endpoint yang ditemukan dan didokumentasikan, file yang dibuat atau diperbarui, serta temuan yang masih perlu ditinjau.

Kerjakan secara bertahap agar hasil tidak terpotong atau hanya berupa kerangka dokumentasi.

## 7. Kriteria Penyelesaian

Pekerjaan dinyatakan selesai apabila:

- Seluruh endpoint API telah diinventarisasi dan didokumentasikan.
- Setiap file mengikuti format standar.
- Penjelasan fungsi fitur dan alur bisnis tersedia.
- Seluruh informasi teknis mengacu pada sumber yang tepat sesuai aturan prioritas.
- Perbedaan antara implementasi dan kebutuhan bisnis dicatat secara jelas.
- Informasi yang belum terverifikasi ditandai sebagai **Perlu Ditinjau**.
- `docs/api/README.md` memuat indeks seluruh dokumentasi.
- Seluruh tautan relatif valid.
- Tidak ada file kosong, terpotong, atau hanya berisi kerangka tanpa penjelasan memadai.

**Hasil akhir yang diharapkan:** dokumentasi API yang dapat digunakan developer lain untuk memahami fungsi fitur, mengetahui perilaku endpoint, melakukan integrasi, dan menelusuri aturan bisnis tanpa harus menebak implementasi aplikasi.