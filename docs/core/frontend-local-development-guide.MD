# Dokumentasi 03: Panduan Koneksi Frontend Lokal ke Server Backend

> [!IMPORTANT]
> **Dokumen Resmi Terpusat:**
> Dokumen ini telah diselaraskan dengan arsitektur multi-environment Tahap 12. Panduan komprehensif seluruh skenario (lokal vs development server vs production guard) kini terpusat di:
> 👉 **[environment-setup-guide.md](environment-setup-guide.md)**.
>
> **Perubahan Kebijakan Sejak Tahap 12:**
> - `npm run dev` secara **default** mengarah ke Backend Lokal (`http://localhost:8000`).
> - Untuk terhubung ke Backend Server Development, gunakan: `npm run dev:server` (membaca konfigurasi `.env.dev-server`).
> - Menghubungkan dev server lokal ke server **Production** (`https://api-jkstok.my.id`) diblokir oleh guard Vite secara default untuk mencegah transaksi uji coba merusak data produksi. Untuk mengizinkannya secara sadar, pasang `VITE_ALLOW_PRODUCTION_PROXY=true`.

---

## 1. Informasi Endpoint Backend Server

* **Domain Backend**: `https://api-jkstok.my.id`
* **Healthcheck**: `https://api-jkstok.my.id/health`
* **API Prefix**: `/api/v1`
* **Full Base URL**: `https://api-jkstok.my.id/api/v1`
* **Status CORS di Server**: Origin `http://localhost:5173`, `http://127.0.0.1:5173`, dan `http://localhost:3000` telah di-whitelist resmi dengan `Access-Control-Allow-Credentials: true`.

---

## 2. Cara Rekomendasi: Menggunakan Vite Development Proxy (Zero-CORS & Zero Cookie Block)

Cara ini adalah standar industri terbaik untuk pengembangan frontend lokal saat backend berada di server HTTPS. Semua request `/api` dari browser lokal akan diteruskan oleh server Vite ke `https://api-jkstok.my.id`.

### Mengapa Vite Proxy Sangat Direkomendasikan?
1. **Bebas Masalah CORS**: Browser menganggap request dikirim ke `http://localhost:5173/api/v1` (origin lokal yang sama).
2. **Cookie Sesi HttpOnly Bekerja Sempurna**: Browser modern (Chrome, Safari) sering memblokir cookie lintas domain (*third-party cookies*) jika website Anda adalah `http://localhost:5173` (HTTP) sedangkan backend adalah `https://api-jkstok.my.id` (HTTPS). Dengan proxy Vite, cookie dianggap sebagai *first-party cookie*.

### Konfigurasi yang Telah Diterapkan di Repositori `warehouse_app/`:

1. **`warehouse_app/vite.config.ts`**:
   ```typescript
   export default defineConfig({
     plugins: [react(), tailwindcss()],
     server: {
       port: 5173,
       proxy: {
         '/api': {
           target: 'https://api-jkstok.my.id',
           changeOrigin: true,
           secure: true,
         },
       },
     },
   });
   ```

2. **`warehouse_app/.env.development`**:
   ```ini
   VITE_API_BASE_URL=/api/v1
   ```

3. **Cara Menjalankan**:
   Cukup jalankan:
   ```bash
   cd warehouse_app
   npm run dev
   ```
   Aplikasi langsung terhubung ke backend server production tanpa konfigurasi tambahan!

---

## 3. Cara Alternatif: Direct Hit ke Domain Server Backend (Cross-Origin)

Jika Anda ingin browser langsung menembak domain backend tanpa melalui proxy Vite:

1. Buat file `warehouse_app/.env.local`:
   ```ini
   VITE_API_BASE_URL=https://api-jkstok.my.id
   ```
   *(Catatan: Jangan tambahkan `/api/v1` di belakangnya karena fungsi `resolveApiBaseUrl()` di `api-client.ts` secara otomatis menyematkan prefix `/api/v1`).*

2. Pastikan port frontend lokal Anda (`http://localhost:5173`) sudah ada di whitelist `FRONTEND_ORIGINS` pada file `.env.production` server backend.

---

## 4. Verifikasi Koneksi dari Browser Lokal

Setelah mengonfigurasi salah satu cara di atas:

### 1. Jalankan Server Frontend Lokal
```bash
npm run dev
```
Aplikasi Anda akan berjalan di `http://localhost:5173`.

### 2. Uji Coba dari Developer Tools (F12)
Buka browser di `http://localhost:5173`, tekan tombol **F12** $\rightarrow$ buka tab **Console**, lalu paste kode berikut untuk menguji koneksi:

```javascript
fetch('https://api-jkstok.my.id/health')
  .then(res => res.json())
  .then(data => console.log('✅ Koneksi Backend Berhasil:', data))
  .catch(err => console.error('❌ Gagal terhubung:', err));
```

Output yang diharapkan di Console:
```json
✅ Koneksi Backend Berhasil: {
  status: "ok",
  service: "WMS REST API",
  version: "2.0.0",
  database: "connected"
}
```

---

## 5. Troubleshooting Masalah Umum

### 1. Error: `CORS policy: No 'Access-Control-Allow-Origin' header is present`
* **Penyebab**: Frontend lokal Anda berjalan di port yang belum terdaftar (misal port `5174` atau `4173`).
* **Solusi**:
  * Pastikan frontend berjalan di port `5173` atau `3000` (port yang telah diizinkan di backend VPS).
  * Atau gunakan **Cara 2 (Vite Proxy)** di atas yang otomatis mem-bypass batasan CORS.

### 2. Error: `Sesi login hilang saat refresh halaman`
* **Penyebab**: Opsi `withCredentials: true` lupa diaktifkan pada instance Axios atau pemanggilan login.
* **Solusi**: Pastikan `withCredentials: true` aktif di `apiClient.ts` dan pada pemanggilan `axios.post('/auth/login', payload, { withCredentials: true })`.

### 3. Masalah Cookie pada Browser Mode Incognito / Safari
* Beberapa browser memblokir cookie pihak ketiga (*Third-Party Cookies*) pada mode Private/Incognito jika request berasal dari domain HTTP (`localhost`) ke HTTPS (`api-jkstok.my.id`).
* **Solusi**: Gunakan **Cara 2 (Vite Development Proxy)** yang secara transparan menyamakan origin ke localhost sehingga cookie tidak dianggap sebagai pihak ketiga.
