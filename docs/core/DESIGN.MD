# Panduan UI/UX Warehouse Management System

Dokumen ini adalah acuan desain untuk frontend WMS. Panduan ini mencakup dua
permukaan produk:

1. **Admin Dashboard** untuk pekerjaan operasional sehari-hari: memantau stok,
   memproses PO dan penerimaan, mengirim transfer, melakukan stock opname, serta
   mengaudit perubahan.
2. **Landing Page** untuk menjelaskan nilai produk kepada pemilik bisnis,
   operations manager, warehouse supervisor, dan calon pengguna sebelum login.

Keduanya memakai identitas yang sama, tetapi tidak memakai kepadatan informasi
yang sama. Dashboard mengutamakan kecepatan keputusan dan akurasi data.
Landing page mengutamakan pemahaman alur kerja dan kepercayaan.

---

## 1. Dasar keputusan desain

### 1.1 Konteks produk

WMS ini bukan dashboard analitik abstrak. Pengguna bekerja dengan objek dan
kejadian yang memiliki konsekuensi nyata:

- item, kategori, UOM, supplier, gudang, dan lokasi;
- saldo stok, stok in-transit, serta stock ledger;
- purchase order dan goods receipt;
- transfer antar gudang;
- stock opname;
- user, role, permission, penugasan gudang, dan audit log.

Karena itu, desain harus membantu pengguna menjawab tiga pertanyaan secara cepat:

1. **Apa yang perlu saya kerjakan sekarang?**
2. **Apa dampaknya terhadap stok dan dokumen terkait?**
3. **Siapa yang melakukan perubahan dan kapan?**

### 1.2 Prinsip utama

1. **Operational clarity** — status, jumlah, lokasi, dan tindakan utama terlihat
   tanpa dekorasi yang mengganggu.
2. **Traceable by default** — aksi bisnis penting selalu memiliki status, waktu,
   aktor, dan jalur menuju detail/audit.
3. **Progressive density** — ringkasan di depan, detail pada tabel atau drawer,
   bukan semua informasi ditumpuk dalam satu layar.
4. **Calm authority** — tampilan profesional dan tegas; gunakan warna untuk
   makna operasional, bukan sekadar hiasan.
5. **One visual language** — dashboard dan landing page berbagi warna, tipografi,
   ikon, radius, dan cara memperlakukan status.

### 1.3 Arah visual: “Warehouse Control Tower”

Identitas visual mengambil inspirasi dari control tower gudang: **ink navy**
sebagai struktur dan kepercayaan, **warm canvas** sebagai permukaan kerja,
serta **amber** sebagai sinyal perhatian dan tindakan. Teal digunakan untuk
pergerakan stok yang sehat dan keberhasilan proses.

Karakter yang diinginkan:

- permukaan terang dan hangat, bukan putih steril;
- panel dengan border tipis dan bayangan sangat ringan;
- satu aksen kuat per konteks, bukan rainbow dashboard;
- angka operasional memakai tabular numerals;
- ikon linear yang menyerupai alat kerja, bukan ilustrasi kartun;
- fotografi/ilustrasi landing page hanya jika menunjukkan konteks gudang yang
  nyata: rak, pallet, barcode, receiving, atau handoff antar lokasi.

Hindari:

- gradient ungu-biru sebagai dekorasi utama;
- dashboard penuh glassmorphism, blur, dan kartu identik;
- KPI yang tidak menghasilkan keputusan;
- badge warna-warni tanpa definisi status;
- ilustrasi generik orang tersenyum di depan grafik;
- judul marketing seperti “revolutionize your inventory” tanpa bukti alur.

---

## 2. Design tokens

Gunakan token CSS/Tailwind, bukan nilai warna ad hoc di tiap komponen.
Nama semantik di bawah lebih penting daripada nama hex-nya; jika brand berubah,
makna komponen tidak ikut berubah.

### 2.1 Palet warna

| Token | Nilai | Penggunaan |
|---|---|---|
| `ink-950` | `#10212B` | teks utama, sidebar dashboard, hero landing |
| `ink-800` | `#1D3540` | heading sekunder, hover permukaan gelap |
| `slate-700` | `#425662` | teks sekunder |
| `slate-500` | `#71828A` | placeholder, metadata, icon sekunder |
| `canvas-50` | `#F7F8F5` | background utama aplikasi |
| `surface-0` | `#FFFFFF` | kartu, tabel, dialog |
| `line-200` | `#DCE3E1` | border dan divider |
| `teal-600` | `#087F78` | primary action, stok sehat, sukses |
| `teal-100` | `#DDF3EF` | background state sukses/aktif |
| `amber-500` | `#D99018` | perhatian, pending, receiving |
| `amber-100` | `#FFF0C9` | background warning |
| `red-600` | `#C2413A` | error, stok kritis, destructive action |
| `red-100` | `#FBE4E1` | background error |
| `blue-600` | `#2D6CDF` | link dan informasi, bukan status utama |
| `blue-100` | `#E5EEFF` | background info |

Aturan penggunaan:

- Background utama memakai `canvas-50`; jangan membuat setiap section memiliki
  warna background sendiri.
- Primary action memakai `teal-600`. Gunakan amber untuk tindakan yang perlu
  perhatian, bukan untuk semua tombol yang terlihat penting.
- Merah hanya untuk risiko, kegagalan, atau aksi destruktif. Jangan gunakan merah
  untuk dekorasi.
- Status tidak boleh dibedakan oleh warna saja. Sertakan label teks atau ikon
  dengan nama yang jelas.
- Kontras teks normal minimal 4.5:1; teks besar minimal 3:1.

### 2.2 Elevation, border, dan radius

| Token | Nilai | Penggunaan |
|---|---|---|
| `radius-sm` | `6px` | input, badge, tombol kecil |
| `radius-md` | `10px` | card, dropdown, table container |
| `radius-lg` | `16px` | hero panel, dialog besar, feature panel |
| `shadow-1` | `0 1px 2px rgb(16 33 43 / 0.06)` | card standar |
| `shadow-2` | `0 12px 30px rgb(16 33 43 / 0.10)` | popover, dialog, floating panel |

Gunakan border `line-200` sebagai pemisah utama. Shadow hanya menunjukkan
elevasi atau interaksi; jangan memberi shadow pada semua elemen.

### 2.3 Spacing dan ukuran kontrol

Gunakan skala 4px: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64`.

- tinggi input dan tombol standar: `40px`;
- kontrol padat di toolbar tabel: `36px`;
- target sentuh minimum: `44px`;
- padding card standar: `24px`;
- jarak antar section halaman: `32px`;
- jarak antar label dan field: `8px`;
- jarak antar field dalam form: `20px`.

---

## 3. Tipografi

Gunakan **Plus Jakarta Sans** atau **Inter** sebagai sans-serif utama. Pilih satu
dan gunakan konsisten; rekomendasi implementasi adalah Plus Jakarta Sans karena
memberi karakter lebih hangat pada landing page namun tetap terbaca di tabel.
Gunakan system fallback untuk menjaga performa:

```css
font-family: "Plus Jakarta Sans", Inter, ui-sans-serif, system-ui, sans-serif;
```

Angka stok, total, dan kuantitas harus memakai `font-variant-numeric:
tabular-nums` agar kolom berubah tanpa melompat secara visual.

| Peran | Ukuran / line-height | Weight | Catatan |
|---|---:|---:|---|
| Display landing | `48/56` desktop, `36/44` mobile | 700 | Maksimal 2 baris |
| Page title | `28/36` | 700 | Nama halaman dashboard |
| Section title | `18/26` | 700 | Judul panel |
| Body | `14/22` atau `16/24` | 400 | Pilih sesuai konteks |
| Label | `12/16` | 600 | Gunakan sentence case |
| Table body | `13/20` atau `14/20` | 400 | Jangan lebih kecil dari 12px |
| KPI value | `28/32` | 700 | `tabular-nums` |
| Caption | `12/16` | 400 | Metadata dan bantuan |

Gunakan sentence case: **“Purchase orders menunggu review”**, bukan
**“PURCHASE ORDERS MENUNGGU REVIEW”**. Uppercase hanya untuk kode dokumen,
status singkat, atau label overline yang sangat terbatas.

---

## 4. Layout dan responsive behavior

### 4.1 Grid umum

- max-width konten landing page: `1200px`;
- max-width area kerja dashboard: `1440px`;
- gutter desktop: `32px`;
- gutter tablet: `24px`;
- gutter mobile: `16px`;
- grid dashboard: 12 kolom desktop, 8 tablet, 4 mobile;
- content dashboard tidak boleh melebar tanpa batas sehingga tabel tetap terbaca.

### 4.2 Admin shell

Desktop:

```text
┌──────────────┬─────────────────────────────────────────┐
│ Sidebar 248  │ Topbar                                  │
│ px           ├─────────────────────────────────────────┤
│              │ Page header + primary action             │
│              ├─────────────────────────────────────────┤
│              │ Content grid / table / detail            │
└──────────────┴─────────────────────────────────────────┘
```

- sidebar lebar `248px`, dapat diciutkan menjadi `72px`;
- topbar tinggi `64px`;
- sidebar memakai `ink-950`, tetapi area kerja memakai `canvas-50`;
- pada mobile sidebar berubah menjadi drawer; jangan mengecilkan sidebar menjadi
  kolom sempit yang sulit disentuh;
- page header selalu memuat breadcrumb atau konteks, judul, deskripsi singkat
  bila perlu, dan satu primary action yang jelas.

### 4.3 Landing page

Gunakan alur naratif, bukan grid 12 kartu fitur:

1. navigation sederhana + CTA login/demo;
2. hero dengan headline berbasis hasil operasional;
3. proof strip berisi metrik atau kapabilitas yang dapat diverifikasi;
4. diagram alur `Receive → Store → Move → Count`;
5. tiga pain point operasional dan jawabannya;
6. screenshot dashboard dalam frame yang realistis;
7. keamanan, traceability, dan role-based access;
8. CTA penutup dan footer.

Hero boleh memakai blok `ink-950` dengan aksen amber/teal yang kecil. Hindari
background penuh gradient; gunakan satu bidang gelap sebagai anchor visual.

Breakpoints:

- `>= 1024px`: dua kolom hero, navigasi penuh, diagram horizontal;
- `768–1023px`: hero tetap dua kolom jika ruang cukup, diagram dapat wrap;
- `< 768px`: satu kolom, CTA full-width atau stacked, screenshot dipotong dengan
  sengaja melalui frame horizontal yang dapat di-scroll.

---

## 5. Komponen UI

### 5.1 Navigation dan shell

- **Sidebar** mengelompokkan menu berdasarkan pekerjaan: Overview, Inventory,
  Procurement, Warehouse Operations, Administration.
- Menu aktif memakai strip teal `3px` di sisi kiri dan permukaan `ink-800`, bukan
  hanya perubahan warna teks.
- Tampilkan badge jumlah hanya untuk pekerjaan yang membutuhkan tindakan, misalnya
  PO pending review atau opname open.
- **Topbar** memuat warehouse switcher, pencarian global, notifikasi, dan menu
  profil. Jangan menaruh lebih dari satu elemen yang membuka menu akun.
- **Breadcrumb** wajib pada detail bertingkat, misalnya
  `Purchase Orders / PO-2026-0042`.

### 5.2 Tombol

- Primary: satu per area kerja, `teal-600`, untuk aksi yang paling diharapkan.
- Secondary: border `line-200`, untuk aksi alternatif.
- Tertiary: text button untuk aksi ringan.
- Destructive: `red-600`, selalu membutuhkan konfirmasi jika berdampak pada data.
- Tombol aksi bisnis harus menyebutkan aksi dan objek: **“Post goods receipt”**,
  bukan **“Submit”**.
- Saat loading, pertahankan lebar tombol dan tampilkan spinner kecil + label
  yang tetap menjelaskan aksi.

### 5.3 Status dan feedback

Gunakan status domain yang konsisten:

| Status | Token | Makna |
|---|---|---|
| Draft | slate | belum siap diproses |
| Pending review | amber | membutuhkan perhatian atau approval |
| Issued / In transit | blue | sudah berjalan, belum selesai |
| Posted / Completed | teal | berhasil menjadi catatan resmi |
| Blocked / Cancelled | red | tidak dapat dilanjutkan atau dibatalkan |

`StatusBadge` selalu menampilkan teks. Ikon hanya memperkuat makna.
Toast untuk hasil singkat; error yang memerlukan tindakan harus tetap terlihat di
halaman melalui `ErrorState`.

### 5.4 Tabel dan filter

Tabel WMS adalah alat kerja utama, bukan kartu yang dibuat menyerupai tabel.

- kolom pertama berisi identifier atau nama objek;
- angka rata kanan dan memakai tabular numerals;
- status diletakkan dekat identifier;
- aksi baris memakai menu `...` hanya jika lebih dari dua aksi;
- header tabel sticky hanya ketika tabel lebih panjang dari viewport;
- filter aktif ditampilkan sebagai chips yang dapat dihapus;
- pagination menyebutkan rentang, misalnya `41–60 dari 238 items`;
- filter dan pagination disimpan di URL agar dapat di-refresh dan dibagikan;
- pada mobile, prioritaskan kolom identifier, status, dan aksi; kolom lainnya
  masuk ke detail drawer, bukan dipaksa menyempit.

### 5.5 Form dan dokumen transaksi

- Form panjang dibagi menjadi section dengan judul yang jelas, bukan accordion
  untuk semua field.
- Field wajib memakai label dan tanda yang konsisten; jangan mengandalkan
  placeholder sebagai label.
- Untuk PO, GR, transfer, dan opname, ringkasan dokumen dibuat sticky di desktop:
  total line, total quantity, status, dan primary action.
- Kuantitas memakai input yang menjaga presisi sesuai `allow_decimal`; tampilkan
  UOM di dekat field.
- Error validasi muncul dekat field dan diringkas di bagian atas form.
- Sebelum aksi yang mengubah stok, tampilkan ringkasan dampak dan objek yang
  akan berubah.

### 5.6 KPI dan chart

KPI dashboard hanya ditampilkan jika pengguna dapat melakukan tindakan setelah
melihatnya. Contoh yang relevan:

- items below reorder level;
- receiving hari ini;
- PO menunggu review;
- transfer in-transit;
- opname yang belum ditutup.

Setiap KPI memuat nilai, label, periode, dan link/drill-down. Hindari pie chart
3D atau chart tanpa unit. Untuk tren, gunakan line/bar chart sederhana dengan
tooltip yang dapat diakses dan tabel ringkasan sebagai alternatif.

---

## 6. Panduan khusus Admin Dashboard

### 6.1 Dashboard overview

Urutan visual yang disarankan:

1. greeting ringkas + warehouse/date scope;
2. alert strip untuk kondisi yang memerlukan tindakan;
3. empat KPI operasional;
4. dua panel kerja: `Needs attention` dan `Recent activity`;
5. tren receiving/dispatch atau stock movement;
6. link cepat ke modul yang sering dipakai.

Jangan menjadikan dashboard sebagai halaman laporan lengkap. Detail tetap berada
di halaman feature agar query, permission, dan konteksnya jelas.

### 6.2 Halaman modul

Setiap modul mengikuti pola:

```text
Page header
├── title, description, breadcrumb
└── primary action
Filter toolbar
Table/list
Pagination
```

Halaman detail mengikuti pola:

```text
Breadcrumb + document identifier + status
Summary panel
Tabs: Overview | Lines | Activity / Audit
Sticky action bar
```

Permission menentukan visibilitas dan enabled state aksi. Jangan hanya
menyembunyikan error setelah pengguna menekan tombol yang sebenarnya tidak
berhak digunakan.

### 6.3 Auth, RBAC, dan audit

- Login memakai layout sederhana dengan panel brand yang tenang; jangan memakai
  form login yang terlalu dekoratif.
- Permission error menjelaskan akses yang kurang dan cara kembali, bukan hanya
  menampilkan “403”.
- Audit log menggunakan format timeline/table: actor, action, object, timestamp,
  request ID atau detail perubahan.
- Data sensitif tidak ditampilkan dalam toast, URL, atau log browser.

---

## 7. Panduan khusus Landing Page

Landing page harus menjual **kendali dan ketertelusuran operasi**, bukan sekadar
menjual daftar library atau fitur.

### 7.1 Pesan

Headline sebaiknya konkret, misalnya:

> **Satu kendali untuk setiap pergerakan stok.**

Supporting copy menjelaskan hasil:

> Pantau saldo per lokasi, proses penerimaan dan transfer, lalu telusuri setiap
> perubahan melalui alur kerja yang sesuai permission.

CTA utama: **“Lihat alur kerja”** atau **“Minta demo”**. CTA login tetap tersedia
di navigation tetapi tidak mengambil perhatian dari CTA utama.

### 7.2 Visual dan bukti

- gunakan screenshot UI yang benar-benar berasal dari dashboard, bukan mockup
  abstrak yang tidak mencerminkan produk;
- tampilkan satu alur konkret: PO → GR → stok bertambah → ledger;
- gunakan label modul yang sama dengan dashboard agar ekspektasi pengguna tepat;
- angka demo harus diberi konteks atau label “contoh data”;
- tampilkan RBAC, auditability, dan multi-warehouse sebagai bukti keandalan,
  bukan klaim kosong.

### 7.3 CTA dan trust

Di bawah hero, tampilkan tiga proof point:

- **Location-level stock** — saldo dapat ditelusuri hingga lokasi;
- **Controlled workflow** — posting dan transfer mengikuti status serta permission;
- **Traceable activity** — perubahan dapat dilihat kembali oleh user yang berwenang.

CTA akhir memakai panel `ink-950` dan satu tombol teal. Jangan menambahkan
pop-up, countdown, atau animasi yang mengganggu pembacaan.

---

## 8. Interaksi, animasi, dan state

### 8.1 Motion

Motion memberi orientasi, bukan hiburan:

- hover tombol/card: `120–160ms`, perubahan warna atau border kecil;
- drawer/dialog: `180–240ms`, ease-out;
- skeleton: shimmer halus atau pulse, tidak lebih dari 1.5 detik per siklus;
- page transition tidak perlu pada dashboard; pertahankan posisi scroll dan
  konteks tabel.

Hormati `prefers-reduced-motion: reduce`: hilangkan transform, parallax, dan
shimmer yang tidak penting.

### 8.2 Loading

- initial page: skeleton mengikuti bentuk akhir, bukan spinner di tengah layar;
- table refetch: pertahankan data lama dan tampilkan indikator kecil di toolbar;
- mutation: disable hanya kontrol yang terlibat, bukan seluruh halaman;
- optimistic update hanya untuk perubahan UI yang dapat dipulihkan; posting stok
  harus menunggu respons server karena memiliki konsekuensi bisnis.

### 8.3 Empty, error, dan offline state

Empty state harus menjawab:

1. apa yang kosong;
2. mengapa mungkin kosong;
3. tindakan berikutnya.

Contoh: **“Belum ada purchase order di warehouse ini. Buat PO pertama atau
ubah filter warehouse.”**

Error state menampilkan pesan yang manusiawi, kode error/request ID jika ada,
dan tombol retry yang kontekstual. Jangan menampilkan stack trace kepada user.
Jika koneksi terputus, bedakan “belum ada data” dari “data gagal dimuat”.

---

## 9. Aksesibilitas dan konsistensi

- semua kontrol keyboard dapat dicapai dengan urutan yang logis;
- focus ring terlihat jelas: minimal `2px` dengan offset `2px`;
- dialog mengunci focus dan kembali ke trigger saat ditutup;
- setiap input memiliki label, deskripsi, dan error yang terhubung secara
  semantik;
- ikon informatif memiliki accessible name; ikon dekoratif memakai
  `aria-hidden`;
- jangan menyampaikan status hanya melalui warna, posisi, atau icon;
- tabel memiliki caption/label konteks dan header yang benar;
- gunakan `aria-live` untuk hasil mutation/toast penting tanpa mengumumkan setiap
  perubahan kecil;
- target sentuh mobile minimal `44x44px`;
- uji dengan keyboard, zoom 200%, layar sempit, dan screen reader dasar;
- format tanggal dan angka mengikuti locale pengguna, tetapi data desimal tetap
  dihitung memakai `decimal.js`.

Checklist sebelum sebuah halaman dianggap selesai:

- [ ] title, breadcrumb, dan primary action jelas;
- [ ] loading, error, empty, dan success state tersedia;
- [ ] permission untuk setiap aksi sudah dipetakan;
- [ ] angka memiliki unit dan format yang benar;
- [ ] filter/pagination dapat direproduksi dari URL;
- [ ] keyboard focus dan contrast sudah diuji;
- [ ] tampilan mobile tidak mengorbankan identifier, status, atau aksi utama;
- [ ] tidak ada card, gradient, chart, atau animasi yang tidak membantu keputusan.

---

## 10. Pemetaan ke struktur frontend

Implementasi mengikuti struktur feature-based pada
[`FOLDER_STRUCTURE.md`](./FOLDER_STRUCTURE.md):

- token dan style global: `src/styles/`;
- layout dan navigasi: `src/components/layout/`;
- primitive UI: `src/components/ui/`;
- komponen WMS lintas modul seperti `DataTable`, `StatusBadge`, `EmptyState`,
  dan `QtyInput`: `src/components/shared/`;
- pola halaman dan aksi per domain: `src/features/<feature>/`;
- format angka, tanggal, permission, dan error: `src/lib/`;
- page composition: `src/pages/`;
- state server: TanStack Query; session dan UI kecil: Zustand.

Jika kebutuhan visual baru tidak dapat dijelaskan oleh token atau komponen yang
ada, tambahkan token/komponen generik terlebih dahulu. Jangan menyelesaikan
perbedaan satu halaman dengan inline style atau warna baru yang hanya dipakai
sekali.