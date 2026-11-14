---
title: Panduan Notifikasi Real-Time Telegram (Error Aplikasi & Docker Monitor)
description: Konfigurasi, arsitektur sanitasi, pengujian, dan SOP deployment pemantauan error aplikasi WMS dan status container Docker via Telegram
document_type: guide
status: approved
version: 1.0
last_updated: 2026-11-14
source_of_truth: true
---

# Panduan Notifikasi Real-Time Telegram (Error Aplikasi & Docker Monitor)

Dokumen ini merupakan panduan resmi **Tahap 13 (Poin 6 & Poin 7)** untuk mengaktifkan sistem observabilitas proaktif pada aplikasi **JejakStok WMS** melalui Telegram Bot HTTP API.

---

## 1. Arsitektur Komponen

Sistem terdiri atas dua jalur pemantauan independen yang mengirim pesan ke Bot Telegram yang sama (atau dipisahkan via `TELEGRAM_THREAD_ID` pada grup bertopik):

| Komponen | Lokasi Kode | Mekanisme Kerja | Cakupan Kondisi |
| :--- | :--- | :--- | :--- |
| **Application Error Alerting (Poin 6)** | `app/core/telegram_alert.py`<br>`app/core/sanitizer.py`<br>`app/main.py` | Terpasang pada global exception handler `Exception`, `HTTPException >= 500`, dan `lifespan` startup DB pool. Pengiriman berjalan **non-blocking** lewat Starlette `BackgroundTask`. | Crash / error HTTP `500` (`INTERNAL_ERROR`), error HTTP `5xx`, dan kegagalan koneksi DB saat startup. Error bisnis valid/terduga (`4xx` / `DomainError`) **tidak** dikirim. |
| **Docker Container Monitor (Poin 7)** | `scripts/docker_telegram_monitor.py` | Skrip Python 3 mandiri (**tanpa dependensi eksternal**) yang mendengarkan stream `docker events` (via CLI atau `/var/run/docker.sock`) ditambah *reconciliation poll* berkala. | **Up** (`start`, `healthy`), **Down** (`die` exit 0 pada service), **Exited** (`die` exit 0 pada job/migrasi), dan **Crash/Restart** (exit != 0, `OOMKilled`, `restart`, crash-loop berulang, `unhealthy`). |

---

## 2. Informasi Terkirim & Jaminan Sanitasi Data Sensitif

### 2.1 Format Informasi Error Aplikasi
Setiap pesan error aplikasi memuat:
- Nama aplikasi / service (`WMS REST API`) dan label environment (`LOCAL` / `DEVELOPMENT` / `STAGING` / `PRODUCTION`).
- Jenis error (nama class exception, mis. `OperationalError`, `RuntimeError`).
- Waktu kejadian dalam **WIB** dan **UTC ISO-8601**.
- **Trace ID / Correlation ID** (`X-Request-ID`) untuk pencocokan langsung dengan log container.
- Endpoint aman (`METHOD /path?query_tersanitasi`) dan HTTP status code.
- Lokasi error pada kode aplikasi (`file:baris (nama_fungsi)`), lokasi terdalam bila berbeda, serta cuplikan stacktrace ringkas (maksimal 5 frame terakhir).

### 2.2 Format Informasi Status Container Docker
Setiap perubahan status container memuat:
- Nama container (mis. `wms_prod_backend`, `wms_prod_postgres`, `wms_prod_frontend`, `wms_prod_migration`).
- Nama service / aplikasi terkait (`backend`, `postgres`, dll. dari label Docker Compose + `APP_NAME`).
- Status perubahan (`UP`, `DOWN`, `EXITED`, `CRASH_RESTART`, `UNHEALTHY`).
- Waktu kejadian (**WIB** + **UTC**) dan nama host server.
- Penyebab kegagalan bila tersedia (`ExitCode`, status `OOMKilled`, `RestartCount`, error Docker State, serta potongan 12 baris log terakhir yang telah disanitasi).

### 2.3 Perlindungan Rahasia & Data Pribadi (PII)
Modul sanitasi (`app/core/sanitizer.py` dan penyaring mandiri di `scripts/docker_telegram_monitor.py`) **wajib** menyamarkan informasi berikut sebelum teks apa pun dikirim ke Telegram atau dicatat ke log kesalahan kirim:
1. Request body HTTP, header `Authorization`, dan cookie sesi **tidak pernah diambil maupun dikirim**.
2. URL koneksi database berkredensial (`postgresql://user:password@host:5432/db` $\rightarrow$ `postgresql://user:[REDACTED]@host:5432/db`).
3. Bot Token Telegram, JWT (`eyJ...`), dan header `Bearer` / `Basic`.
4. Pasangan field/parameter kueri sensitif (`password`, `secret`, `token`, `api_key`, `cookie`, `email`, `phone`, `no_hp`, `alamat`, `nik`, `npwp`, `ktp`).
5. Alamat email berdiri sendiri (`[REDACTED_EMAIL]`), detail constraint PostgreSQL `Key (email)=(...)`, dan nomor ponsel Indonesia (`[REDACTED_PHONE]`).

### 2.4 Anti-Flood & Rate Limit Guard
Untuk mencegah pemblokiran API Telegram (HTTP `429 Too Many Requests`) saat terjadi lonjakan error beruntun atau container *crash-loop* tiap detik:
- **Backend Error**: Menerapkan cooldown per kombinasi `(error_type, lokasi, path)` selama `TELEGRAM_COOLDOWN_SECONDS` (default `60` detik).
- **Docker Monitor**: Transisi status normal (`UP` $\leftrightarrow$ `DOWN`) dikirim seketika; bila container mengalami crash berulang mencapai `DOCKER_MONITOR_CRASH_THRESHOLD` (default `2` kali dalam `DOCKER_MONITOR_CRASH_WINDOW_SECONDS=300` detik), eskalasi dikirim sekali lalu *flapping* ditahan selama `DOCKER_MONITOR_COOLDOWN_SECONDS` (default `30` detik). Jumlah event yang tertahan dilaporkan pada notifikasi berikutnya.

---

## 3. Setup Bot Telegram & Konfigurasi Environment

### 3.1 Membuat Bot & Mendapatkan Chat ID
1. Buka **[@BotFather](https://t.me/BotFather)** di Telegram, jalankan `/newbot`, beri nama bot, lalu catat **HTTP API Token**.
2. Untuk menerima notifikasi di **chat pribadi**: kirim pesan pembuka (mis. `hallo`) ke bot Anda, lalu buka `https://api.telegram.org/bot<TOKEN_ANDA>/getUpdates` dan catat nilai `result[0].message.chat.id`.
3. Untuk menerima notifikasi di **grup tim teknis** *(direkomendasikan)*:
   - Tambahkan bot ke grup Telegram tim Anda.
   - Kirim satu pesan `@NamaBot halo` di dalam grup tersebut, lalu cek `getUpdates` untuk mengambil `chat.id` (bernilai negatif, mis. `-100xxxxxxxxxx`).
   - Jika grup memakai fitur **Topics**, catat juga `message_thread_id` topik tujuan.

### 3.2 Variabel Environment
Tambahkan variabel berikut pada berkas konfigurasi aktif (`.env` / `.env.local` di lokal, atau `/opt/wms/.env.production` di server). **Jangan pernah menyimpan token asli ke berkas Git.**

```env
# --- Notifikasi Error & Docker Monitor via Telegram ---
TELEGRAM_ENABLED=True
TELEGRAM_BOT_TOKEN=<ganti-dengan-token-bot-dari-botfather>
TELEGRAM_CHAT_ID=<ganti-dengan-chat-id-atau-group-id>
# Opsional: isi angka ID topik jika mengirim ke Telegram Group bertopik
TELEGRAM_THREAD_ID=
TELEGRAM_TIMEOUT_SECONDS=5.0
TELEGRAM_COOLDOWN_SECONDS=60

# Konfigurasi daemon scripts/docker_telegram_monitor.py
APP_NAME=JejakStok WMS
DOCKER_MONITOR_FILTERS=wms
DOCKER_MONITOR_COOLDOWN_SECONDS=30
DOCKER_MONITOR_CRASH_WINDOW_SECONDS=300
DOCKER_MONITOR_CRASH_THRESHOLD=2
DOCKER_MONITOR_POLL_INTERVAL_SECONDS=30
DOCKER_MONITOR_LOG_LINES=12
```

> [!TIP]
> Gunakan bot atau `TELEGRAM_THREAD_ID` terpisah antara server **development/staging** dan **production** agar engineer dapat langsung membedakan tingkat urgensi insiden.

---

## 4. Pengujian & Simulasi Lokal

Jalankan perintah berikut dari root repositori `api_warehouse_app/`:

1. **Simulasi Format Payload Tanpa Mengirim ke Internet (`--dry-run`)**:
   ```powershell
   .\venv\Scripts\python.exe scripts/docker_telegram_monitor.py --test --dry-run
   ```
2. **Uji Kirim Notifikasi Error Aplikasi ke Telegram**:
   ```powershell
   .\venv\Scripts\python.exe -m app.core.telegram_alert --test
   ```
3. **Uji Kirim Notifikasi Status Container Docker ke Telegram**:
   ```powershell
   .\venv\Scripts\python.exe scripts/docker_telegram_monitor.py --test
   ```
4. **Uji Sekali Jalan Snapshot Container Lokal (`--once`)**:
   ```powershell
   .\venv\Scripts\python.exe scripts/docker_telegram_monitor.py --once --dry-run
   ```

> [!NOTE]
> Jika koneksi internet/ISP lokal Anda memblokir atau memutus TLS handshake menuju `api.telegram.org:443` (`The handshake operation timed out`), pengujian unit di `pytest` tetap berjalan 100% offline dengan `httpx.MockTransport`, dan aplikasi WMS tidak akan terblokir atau crash ketika pengiriman Telegram gagal. Set `TELEGRAM_ENABLED=False` pada `.env` PC lokal apabila jaringan lokal tidak terhubung ke Telegram API.

---

## 5. Deployment di Server Production (`/opt/wms/`)

Di VPS Ubuntu production, backend API sudah otomatis mengirim notifikasi error aplikasi selama `TELEGRAM_ENABLED=True` ada di `/opt/wms/.env.production`. Untuk mengaktifkan **Docker Container Monitor (Poin 7)**, pilih salah satu metode di bawah ini.

### Metode A (Direkomendasikan): Service `systemd` di Host Server
Metode ini memakai Python 3 bawaan Ubuntu tanpa perlu membangun image Docker tambahan, berjalan sebagai user `deployer` yang sudah tergabung dalam grup `docker`.

1. Salin skrip monitor ke server:
   ```bash
   sudo -u deployer mkdir -p /opt/wms/scripts
   # Dari komputer lokal atau via raw copy dari repositori:
   scp api_warehouse_app/scripts/docker_telegram_monitor.py deployer@<IP_SERVER_PROD>:/opt/wms/scripts/docker_telegram_monitor.py
   chmod 700 /opt/wms/scripts/docker_telegram_monitor.py
   ```
2. Uji pengiriman dari server:
   ```bash
   python3 /opt/wms/scripts/docker_telegram_monitor.py --env-file /opt/wms/.env.production --test
   ```
3. Buat unit service `systemd`:
   ```bash
   sudo tee /etc/systemd/system/wms-docker-monitor.service >/dev/null <<'EOF'
   [Unit]
   Description=JejakStok WMS Docker Container Telegram Monitor
   After=docker.service network-online.target
   Requires=docker.service
   Wants=network-online.target

   [Service]
   Type=simple
   User=deployer
   Group=docker
   WorkingDirectory=/opt/wms
   ExecStart=/usr/bin/python3 /opt/wms/scripts/docker_telegram_monitor.py --env-file /opt/wms/.env.production
   Restart=always
   RestartSec=5
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   EOF
   ```
4. Aktifkan dan pantau log daemon:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now wms-docker-monitor
   sudo systemctl status wms-docker-monitor
   sudo journalctl -u wms-docker-monitor -n 30 --no-pager
   ```
5. **Uji Simulasi Container Stop/Start/Restart** *(lakukan di luar jam sibuk / pada dev server)*:
   ```bash
   docker restart wms_prod_backend
   # Periksa Telegram: notifikasi DOWN/UP harus masuk dalam hitungan detik
   ```

### Metode B (Alternatif): Sidecar Service di `docker-compose.prod.yml`
Jika Anda lebih memilih menjalankan monitor sebagai container di dalam `/opt/wms/docker-compose.prod.yml`, backend image sudah menyertakan Python 3.12 dan skrip monitor yang mendukung mode socket Unix (`--backend socket`):

```yaml
  docker-monitor:
    image: ghcr.io/rayhanyl/api_warehouse_app/wms-backend:latest
    container_name: wms_prod_monitor
    restart: always
    env_file: .env.production
    # Berjalan sebagai root atau GID grup docker host agar dapat membaca /var/run/docker.sock:ro
    user: "0:0"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    command: ["python", "/app/scripts/docker_telegram_monitor.py", "--backend", "socket"]
    networks:
      - wms_internal
```
*(Catatan keamanan: tetap batasi mount socket dengan `:ro` agar monitor hanya dapat membaca event/inspect/log dan tidak dapat memodifikasi container lain).*

---

## 6. Prosedur Keamanan & Rotasi Token Bot

- Simpan `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID` **hanya** di berkas `.env.production` dengan izin `chmod 600 /opt/wms/.env.production`.
- **Dilarang keras** melakukan commit token bot asli ke Git (`.env.example`, dokumentasi, atau kode uji).
- Apabila token bot pernah dibagikan melalui chat, tangkapan layar, atau riwayat log eksternal sebelum masuk ke server produksi, lakukan rotasi segera via `@BotFather` menggunakan perintah `/revoke` $\rightarrow$ pilih bot Anda $\rightarrow$ perbarui `TELEGRAM_BOT_TOKEN` di `/opt/wms/.env.production` $\rightarrow$ recreate container backend dan restart `wms-docker-monitor`.
