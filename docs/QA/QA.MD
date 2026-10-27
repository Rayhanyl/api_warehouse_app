# Panduan QA WMS

Dokumen ini menggabungkan rencana dan spesifikasi QA WMS dalam satu tempat. Cakupan dibagi menjadi QA **Backend** untuk REST API yang telah tersedia dan QA **Frontend** sebagai rencana untuk klien antarmuka yang mungkin dibangun terpisah.

| Informasi | Keterangan |
| --- | --- |
| Produk | Warehouse Management System (WMS) REST API |
| Acuan utama | `docs/core/PRODUCT_REQUIREMENTS_DOCUMENT.md` (PRD v2.0) |
| Acuan struktur | `docs/core/FOLDER_STRUCTURE.md` |
| Backend saat ini | Python, FastAPI, PostgreSQL, `pytest` dan `httpx` |
| Database pengujian | PostgreSQL `wms_test` |
| Status frontend | Belum termasuk MVP; tidak ada aplikasi frontend di repository ini |

## 1. Tujuan dan cara menggunakan

Panduan ini membantu menentukan apa yang perlu diuji, urutan prioritas, dan bukti yang perlu dicatat. PRD dan acceptance criteria (AC-01 s.d. AC-14) tetap menjadi sumber kebenaran untuk perilaku sistem. Isi dokumen QA lama yang digabungkan di sini adalah bahan rujukan; daftar alat atau skenario yang berstatus rencana bukan berarti alat tersebut sudah dipasang atau dijalankan.

Jalankan pengujian backend hanya pada database khusus `wms_test`. Jangan arahkan test/reset fixture ke database pengembangan atau produksi. Test database menggunakan PostgreSQL sungguhan; mock boleh digunakan untuk menguji bagian frontend secara terisolasi bila frontend kelak tersedia, tetapi tidak menggantikan verifikasi backend terhadap PostgreSQL.

Perintah dasar:

```powershell
pytest
pytest -k ac06
```

Jangan mencatat suatu skenario sebagai lulus sebelum test atau pemeriksaan yang sesuai benar-benar dijalankan dan hasilnya disimpan.

## 2. QA Backend — REST API

### 2.1. Cakupan saat ini

Prioritaskan kebenaran transaksi stok, hak akses, dan integritas ledger. Test otomatis yang tersedia menggunakan `pytest`/`httpx` dan PostgreSQL nyata. Test AC yang ada berada di berkas berikut.

| Area | Lokasi test |
| --- | --- |
| Autentikasi dan refresh token | `tests/test_auth.py` |
| RBAC, warehouse scoping, master data | `tests/test_rbac_scoping.py` |
| Menu navigasi dinamis | `tests/test_menus.py` |
| Goods Receipt dan posting PO | `tests/test_goods_receipt.py` |
| Transfer stok | `tests/test_stock_transfer.py` |
| Stock Opname | `tests/test_stock_opname.py` |
| Append-only ledger dan audit log | `tests/test_immutability.py` |
| Request ID | `tests/test_request_id.py` |

### 2.2. Acceptance criteria

Gunakan matriks ini sebagai daftar regresi wajib. Nama test ditulis sesuai implementasi di repository.

| AC | Yang diverifikasi | Test |
| --- | --- | --- |
| AC-01 | GR parsial, batas over-receipt, dan pemenuhan PO | `test_ac01_partial_receipt_over_receipt_and_po_fulfillment` |
| AC-02 | Stok negatif ditolak atau diizinkan sesuai konfigurasi gudang | `test_ac02_negative_stock_prevention_and_allow_negative_stock_flag` |
| AC-03 | Konsistensi transfer antar-gudang, stok in-transit, dan scoping | `test_ac03_inter_warehouse_transfer_consistency_in_transit_and_scoping` |
| AC-04 | Rekonsiliasi Opname, selisih, dan tanpa ledger untuk selisih nol | `test_ac04_stock_opname_reconciliation_variance_and_zero_variance_no_ledger` |
| AC-05 | Penegakan RBAC dan pencatatan audit log | `test_ac05_rbac_enforcement_and_audit_log_recording` |
| AC-06 | Pengiriman transfer bersamaan tidak membuat saldo negatif | `test_ac06_concurrent_ship_only_one_succeeds` |
| AC-07 | Kegagalan posting GR me-rollback seluruh transaksi | `test_ac07_gr_post_transaction_atomicity_rollback_on_failure` |
| AC-08 | `stock_movements` dan `audit_logs` tidak dapat diubah/dihapus | `test_ac08_immutability_stock_movements_and_audit_logs` |
| AC-09 | Validasi kuantitas terima transfer dan pencatatan selisih | `test_ac09_transfer_receipt_variance_validation_and_accounting` |
| AC-10 | Lokasi dibekukan selama Opname dan dibuka kembali pada akhir/saat pembatalan | `test_ac10_location_freeze_during_opname_and_unfreeze_on_complete_or_cancel` |
| AC-11 | Rotasi refresh token, deteksi pemakaian ulang, dan logout | `test_ac11_refresh_token_rotation_reuse_detection_and_logout` |
| AC-12 | Penugasan gudang dan penolakan akses di luar cakupan | `test_ac12_warehouse_scoping_assignment_and_access_enforcement` |
| AC-13 | Dua posting GR bersamaan tidak mem-posting dokumen dua kali | `test_ac13_concurrent_gr_post_prevents_double_posting` |
| AC-14 | Pohon menu terfilter permission, akses administrasi, audit, validasi parent, dan penonaktifan tanpa hard delete | `test_ac14_menu_tree_filters_permissions_and_keeps_visible_parents`; `test_ac14_menu_admin_permission_crud_and_audit_log`; `test_ac14_menu_parent_validation_and_soft_deactivation` |

Test AC-06 dan AC-13 harus tetap diuji dengan konkurensi nyata: koneksi database terpisah dan sinkronisasi dua request. Jangan menggantinya dengan test berurutan atau mock, karena itu tidak menguji perlombaan transaksi.

### 2.3. Pemeriksaan backend tambahan

Lakukan pemeriksaan berikut saat perubahan menyentuh area terkait, lalu masukkan ke regresi sebelum rilis:

| Prioritas | Pemeriksaan | Hasil yang diharapkan |
| --- | --- | --- |
| P0 | Autentikasi, token kedaluwarsa/revoked, lockout login, pengguna nonaktif | HTTP dan kode error sesuai Lampiran B PRD; status/peran diambil dari DB setiap request |
| P0 | Permission dan gudang di luar penugasan | Akses ditolak; tidak ada data lintas gudang yang bocor |
| P0 | Siklus status PO, GR, Transfer, dan Opname | Hanya aksi/transisi sah yang berhasil; transisi ilegal ditolak |
| P0 | Saldo, ledger, audit, dan rollback | Setiap mutasi saldo melewati service pergerakan stok dan menghasilkan ledger; transaksi gagal tidak meninggalkan perubahan parsial |
| P0 | Kuantitas dan validasi UoM | Kuantitas memakai desimal tanpa kehilangan presisi; UoM bilangan bulat menolak pecahan; JSON menggunakan string desimal |
| P1 | Validasi request dan katalog error | Field wajib, ID tidak valid, kuantitas nol/negatif, batas penerimaan, serta kode/status HTTP cocok dengan kontrak |
| P1 | Filter, pagination, dan pengurutan | Hasil stabil, batas halaman benar, filter bekerja, dan kolom sort dibatasi whitelist |
| P1 | Audit dan informasi sensitif | Aksi penting tercatat; password, hash, token, dan rahasia tidak masuk log/audit/error |
| P1 | Skema dan migrasi | Migrasi berurutan dapat diterapkan; FK, constraint, dan role aplikasi menjaga integritas/immutability |
| P2 | Request ID dan dokumentasi OpenAPI | Request ID tersedia pada respons; kontrak OpenAPI sejalan dengan endpoint dan schema yang terimplementasi |

### 2.4. Kinerja query stok dan ledger

PRD 7.3 menetapkan waktu respons baca saldo stok dan pencarian master data di bawah **200 ms pada p95** untuk beban normal, dengan asumsi awal hingga 20 pengguna bersamaan, 10.000 barang aktif, dan 1.000.000 baris ledger.

Untuk query stok dan ledger yang paling sering digunakan:

1. Jalankan `EXPLAIN ANALYZE` pada PostgreSQL dengan volume data yang mewakili asumsi tersebut.
2. Catat query, jumlah baris, indeks yang dipakai, rencana eksekusi, dan waktu aktual. Periksa pemindaian penuh, estimasi baris yang meleset, serta biaya join dan sort.
3. Ukur juga waktu respons API secara berulang pada beban yang dinyatakan; laporkan p50/p95 dan konfigurasi lingkungan. `EXPLAIN ANALYZE` sendiri bukan pengukuran p95 API.
4. Jika target tidak tercapai, optimalkan query atau indeks sesuai skema PRD, kemudian ulangi pengukuran dan simpan perbandingan sebelum/sesudah.

Catatan M8 di `docs/API/README.md` memuat benchmark lokal yang pernah dilakukan. Catatan tersebut bukan jaminan p95 di lingkungan produksi dan harus dibaca bersama batasan dataset serta lingkungan yang tercantum di sana.

### 2.5. Kriteria selesai QA backend

- Seluruh AC yang terdampak perubahan lulus; sebelum rilis, suite AC-01 s.d. AC-14 lulus.
- AC-14 menguji menu pada PostgreSQL nyata; permission menu hanya menyaring navigasi dan tidak menggantikan otorisasi endpoint backend.
- Status run terbaru saat pembaruan dokumentasi: 21 tes lulus di `wms_test`, termasuk ketiga tes AC-14.
- Tidak ada temuan terbuka yang mengancam integritas saldo/ledger, autentikasi, atau pembatasan akses.
- Pemeriksaan saldo, ledger, audit, dan rollback konsisten dengan PRD.
- Kinerja dilaporkan dengan lingkungan, ukuran data, metode, dan hasil p95; klaim target hanya dibuat bila hasilnya memang terukur.
- Bukti run, commit/build, konfigurasi, dan temuan tersimpan sehingga hasil dapat diulang.

## 3. QA Frontend — rencana untuk klien terpisah

### 3.1. Status dan batas cakupan

PRD 2.2 mengecualikan antarmuka pengguna dari MVP. Repository ini menyediakan REST API dan dokumentasi/Swagger; saat ini tidak ada aplikasi frontend untuk diuji. Bagian ini adalah checklist masa depan jika klien web atau perangkat genggam dibangun secara terpisah. Skenario tidak boleh dilaporkan sebagai sudah diuji sebelum klien tersedia.

### 3.2. Skenario alur pengguna

Ketika frontend tersedia, uji tiap alur dengan akun sesuai peran dan penugasan gudang:

| Alur | Yang diperiksa pada antarmuka |
| --- | --- |
| Login dan sesi | Validasi isian, login gagal/terkunci, logout, token kedaluwarsa, dan kembali ke login tanpa menampilkan token |
| Master data dan PO | Form wajib, nilai kuantitas, baris item, status PO, dan pesan validasi server |
| GR | Pemilihan PO/baris/lokasi, penerimaan parsial, batas sisa PO, posting, serta pembaruan stok/status |
| Transfer | Gudang/lokasi asal dan tujuan, persetujuan, pengiriman, status in-transit, penerimaan penuh/kurang, dan alasan selisih wajib |
| Stock Opname | Mulai sesi, lokasi beku, input hasil hitung, pengajuan, persetujuan/penolakan, dan selisih yang menghasilkan penyesuaian |
| Saldo dan ledger | Filter lokasi/gudang/barang, pagination, urutan waktu, kuantitas desimal, serta navigasi ke dokumen referensi |
| Akses per peran | Pohon menu dari `GET /api/v1/menus/my-menu` sesuai permission; respons 403 dari API tetap ditangani dengan benar. Penyaringan menu tidak menggantikan kontrol permission API. |

### 3.3. Pengalaman, aksesibilitas, dan ketahanan

- Tampilkan loading, kosong, sukses, validasi, konflik status, tidak berizin, dan gangguan jaringan dengan pesan yang bisa ditindaklanjuti.
- Cegah klik ganda pada aksi transaksi dan tampilkan hasil status terbaru. Jangan mengulang aksi non-idempoten otomatis setelah timeout tanpa memastikan status dari API.
- Jangan mengandalkan penyembunyian tombol sebagai kontrol keamanan; API tetap menjadi otoritas permission dan warehouse scoping.
- Uji keyboard, fokus, label form, pembacaan error, kontras, zoom, dan layout pada ukuran layar yang dipakai operator.
- Pastikan kuantitas tidak dibulatkan secara diam-diam dan format yang ditampilkan tetap sesuai presisi API/UoM.
- Pastikan log browser dan pesan kesalahan tidak mengekspos token, password, atau data sensitif.

### 3.4. Lapisan uji frontend yang disarankan

Pilih teknologi setelah keputusan frontend dibuat; daftar ini tidak menambahkan dependensi ke backend saat ini.

1. **Unit/komponen:** validasi form, format angka, label/status, dan tampilan berdasarkan permission.
2. **Integrasi klien-API:** kontrak request/response dan penanganan error; mock boleh untuk mengisolasi komponen.
3. **End-to-end:** jalankan alur utama terhadap API dan database uji/staging dengan data uji terisolasi, termasuk skenario multi-peran.
4. **Lintas browser/perangkat:** uji browser dan perangkat yang benar-benar ditargetkan operator; pengujian perangkat genggam hanya relevan jika klien tersebut disepakati.

## 4. Prioritas dan pelaporan temuan

Urutan prioritas: **P0** integritas stok/ledger, transaksi atomik, autentikasi, permission, dan scoping; **P1** validasi, state machine, filter/pagination, error handling, dan audit; **P2** kinerja, aksesibilitas, responsivitas, dan kompatibilitas klien.

Untuk setiap temuan, catat:

- ID, tanggal, prioritas/keparahan, lingkungan, versi/build, dan peran pengguna.
- Prasyarat/data uji dan langkah reproduksi yang singkat.
- Hasil yang diharapkan menurut PRD dan hasil aktual, termasuk status HTTP/kode error atau dampak UI.
- Bukti yang aman (request/response yang sudah disamarkan, log tanpa rahasia, screenshot bila UI tersedia).
- Status perbaikan dan hasil verifikasi ulang.

## 5. Referensi

- `docs/CORE/PRODUCT_REQUIREMENTS_DOCUMENT.MD` — FR, aturan bisnis, AC-01 s.d. AC-14, dan target kinerja.
- `docs/CORE/FOLDER_STRUCTURE.MD` — struktur aplikasi dan urutan tahap implementasi.
- `docs/API/README.md` — indeks dokumentasi endpoint dan catatan penyelesaian implementasi.
- `tests/` — implementasi skenario otomatis backend.
