---
title: Keamanan Server dan Aplikasi WMS
description: Konfigurasi, tujuan, dan prosedur pemeriksaan pengamanan server (SSH, firewall, database, secret, backup, monitoring) serta aplikasi JejakStok
document_type: guide
status: draft
version: 1.0
last_updated: 2026-11-13
source_of_truth: true
---

# Keamanan Server dan Aplikasi WMS

Dokumen ini menjelaskan pengamanan yang **diterapkan di aplikasi** dan yang **harus dijalankan
di server**, lengkap dengan tujuan dan cara memeriksanya. Konteks deployment (Ubuntu, Docker
Compose, Nginx di host, GitHub Actions) mengikuti [DEPLOYMENT_GUIDE_CICD.md](DEPLOYMENT_GUIDE_CICD.md);
cara mengelola environment mengikuti [environment-setup-guide.md](environment-setup-guide.md).

## 0. Cara membaca status

| Label | Arti |
| --- | --- |
| **Aktual** | Terverifikasi pada kode/repositori pada 2026-11-13 |
| **Jalankan di server** | Perintah untuk dieksekusi pemilik server. Belum dijalankan atau diverifikasi dari repositori |
| **Rekomendasi** | Perbaikan yang belum ada; perlu keputusan atau uji di server development lebih dulu |

> [!NOTE]
> Perintah server di bawah ditulis untuk Ubuntu 22.04/24.04 dan pengguna `deployer` pada
> `/opt/wms`. Nilai dalam `<kurung siku>` adalah placeholder yang Anda isi sendiri.
> Jalankan setiap blok pada server development lebih dulu bila memungkinkan.

## 1. Tindakan mendesak: rahasia produksi pernah terpublikasi

**Temuan (Aktual).** Pada commit `963bc61` (2026-11-12 16:03 +07) berkas
`docs/core/DEPLOYMENT_GUIDE_CICD.md` memuat nilai asli berikut dan repositori
`api_warehouse_app` berstatus **publik** di GitHub:

| Rahasia yang terpapar | Dampak jika disalahgunakan |
| --- | --- |
| `JWT_SECRET` production | Siapa pun dapat menerbitkan access token palsu (HS256) sebagai pengguna mana pun termasuk Super Admin, selama token berumur sebelum secret diganti |
| Password role `wms_owner` | Akses penuh ke database jika port database dapat dijangkau (lihat §4) |
| Alamat IP server dan nama pengguna SSH | Memudahkan pemindaian dan serangan brute-force SSH |

Nilai tersebut sudah dihapus dari versi terbaru dokumen, tetapi **tetap ada di riwayat Git
dan mungkin sudah disalin pihak lain**. Menghapusnya dari riwayat tidak menjamin salinan
lain hilang, sehingga **rotasi adalah satu-satunya perbaikan yang pasti**.

### 1.1 Prosedur rotasi (Jalankan di server, urutan ini)

1. **Rotasi `JWT_SECRET`.** Refresh token berupa string acak yang disimpan ter-hash di database
   (bukan JWT), jadi sesi pengguna tidak terputus: access token lama gagal, lalu klien
   otomatis mendapat yang baru lewat refresh.

   ```bash
   cd /opt/wms
   openssl rand -hex 32          # salin hasilnya
   nano .env.production          # ganti nilai JWT_SECRET= dengan hasil di atas
   ```

2. **Rotasi password `wms_owner`.** Perubahan `POSTGRES_PASSWORD` di berkas env tidak mengubah
   password role yang sudah ada, jadi ubah di database dan di berkas env. Gunakan password
   alfanumerik agar aman di URL koneksi.

   ```bash
   NEW_PW=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | cut -c1-40)
   DB_USER=$(grep -E '^POSTGRES_USER=' /opt/wms/.env.production | cut -d= -f2-)
   DB_NAME=$(grep -E '^POSTGRES_DB=' /opt/wms/.env.production | cut -d= -f2-)
   echo "ALTER ROLE ${DB_USER} WITH PASSWORD '${NEW_PW}';" \
     | docker exec -i wms_prod_postgres psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1
   echo "Password baru: ${NEW_PW}"    # tempel ke POSTGRES_PASSWORD, DATABASE_URL, MIGRATION_DATABASE_URL
   nano /opt/wms/.env.production
   unset NEW_PW
   ```

3. **Terapkan ulang** seluruh container agar membaca env baru
   (`up -d --force-recreate`, lihat bagian 10.A.5 pada
   [DEPLOYMENT_GUIDE_CICD.md](DEPLOYMENT_GUIDE_CICD.md)), lalu uji login dan
   `curl -s https://api-jkstok.my.id/health`.
4. **Telusuri jejak penyalahgunaan.** Aktivitas tulis tercatat di `audit_logs`. Bandingkan
   alamat IP sejak waktu paparan dengan IP yang Anda kenal:

   ```sql
   SELECT ip_address, count(*) AS jumlah, min(created_at) AS pertama, max(created_at) AS terakhir
   FROM audit_logs
   WHERE created_at >= '2026-11-12 16:03:00+07'
   GROUP BY ip_address ORDER BY jumlah DESC;
   ```

   Alamat IP akan akurat hanya bila `TRUSTED_PROXY_IPS` sudah diatur (lihat §3.4); jika belum,
   semua baris menunjukkan IP proxy. Akses baca tidak diaudit sehingga tidak dapat dilacak
   dengan cara ini.
5. **Opsional: bersihkan riwayat Git** dengan `git filter-repo --replace-text` lalu force-push.
   Ini mengurangi paparan baru tetapi tidak membatalkan salinan yang sudah ada, dan memaksa
   semua klon ulang. Lakukan hanya jika diperlukan dan setelah koordinasi tim.
6. Aktifkan **GitHub secret scanning dan push protection** (Settings, Code security) agar
   kebocoran serupa terblokir sebelum ter-push.

Status: **Jalankan di server** (belum dilakukan oleh pengembang dokumen ini).

## 2. Pengamanan akses server dan SSH

| Kontrol | Tujuan | Status |
| --- | --- | --- |
| Login SSH hanya dengan kunci, root dinonaktifkan | Menutup brute-force password | Jalankan di server |
| `fail2ban` untuk SSH | Memblokir IP yang berulang gagal login | Jalankan di server |
| `ufw limit` pada SSH | Membatasi laju koneksi baru | Jalankan di server |
| Pembaruan keamanan otomatis | Menutup kerentanan OS tanpa menunggu | Jalankan di server |
| Pengguna `deployer` tanpa `sudo`, kunci khusus CI | Membatasi dampak kunci CD yang bocor | Aktual (desain, §6.2 deployment) |

### 2.1 Hardening SSH

> [!WARNING]
> Pertahankan satu sesi SSH terbuka sampai sesi kedua terbukti bisa masuk dengan kunci. Salah
> konfigurasi dapat mengunci Anda dari server.

Berkas drop-in dibaca berurutan dan **nilai pertama menang**. Image cloud Ubuntu sering
memiliki `50-cloud-init.conf` dengan `PasswordAuthentication yes`, jadi beri nama berkas kita
dengan awalan `01-` agar terbaca lebih dulu.

```bash
sudo tee /etc/ssh/sshd_config.d/01-wms-hardening.conf >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
MaxAuthTries 3
LoginGraceTime 30
AllowUsers <user_admin> deployer
EOF
sudo sshd -t && sudo systemctl reload ssh
```

Pemeriksaan (nilai efektif harus sesuai, bukan sekadar isi berkas):

```bash
sudo sshd -T | grep -E '^(passwordauthentication|permitrootlogin|maxauthtries|allowusers) '
# dari PC lain, harus ditolak dengan "Permission denied (publickey)":
ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no <user>@<host>
```

Mengubah port SSH tidak dianjurkan sebagai langkah awal: Ubuntu 24.04 memakai aktivasi
`ssh.socket` sehingga perubahan port memerlukan konfigurasi tambahan, dan Anda harus
menyesuaikan UFW serta secret `PROD_SERVER_PORT`. `fail2ban` memberi manfaat lebih besar.

### 2.2 fail2ban dan pembatasan laju

```bash
sudo apt install -y fail2ban unattended-upgrades
sudo tee /etc/fail2ban/jail.d/wms-sshd.local >/dev/null <<'EOF'
[DEFAULT]
ignoreip = 127.0.0.1/8 <IP_ADMIN_STATIS_JIKA_ADA>

[sshd]
enabled  = true
backend  = systemd
maxretry = 5
findtime = 10m
bantime  = 1h
EOF
sudo systemctl enable --now fail2ban
sudo ufw limit OpenSSH
sudo dpkg-reconfigure -plow unattended-upgrades
```

Pemeriksaan: `sudo fail2ban-client status sshd` (jail aktif), `sudo ufw status verbose`
(aturan SSH bertanda `LIMIT`), `systemctl status unattended-upgrades`.

### 2.3 Kunci CI/CD

Pengguna `deployer` berada di grup `docker`, yang setara akses root pada host. Karena itu:
gunakan kunci ed25519 khusus GitHub Actions (jangan pakai kunci pribadi Anda), jangan beri
`sudo`, putar kunci bila ada pergantian anggota tim atau dugaan kebocoran, dan simpan hanya
di GitHub Secrets (`PROD_SERVER_SSH_KEY`).

## 3. Firewall, port, dan reverse proxy

### 3.1 Port yang diizinkan

| Port | Layanan | Boleh dari internet | Cara dipastikan |
| --- | --- | :---: | --- |
| 22 | SSH | Ya (dibatasi, `fail2ban`) | UFW `LIMIT` |
| 80, 443 | Nginx host | Ya | UFW `Nginx Full` |
| 5432 | PostgreSQL | **Tidak** | Dipublikasikan hanya ke `127.0.0.1` pada compose production |
| 8000 | Backend | **Tidak** | `127.0.0.1:8000` |
| 3000 | Frontend | **Tidak** | `127.0.0.1:3000` |

> [!IMPORTANT]
> Docker memasang aturan `iptables` sendiri sehingga port yang dipublikasikan **melewati UFW**.
> UFW saja tidak melindungi container. Perlindungan sebenarnya adalah pengikatan ke
> `127.0.0.1` pada `docker-compose.prod.yml` (Aktual, bagian 6.4 deployment). File
> `docker-compose.yml` di repositori backend adalah untuk pengembangan lokal dan
> mempublikasikan port API ke semua antarmuka; jangan dipakai di server.

Pemeriksaan di server dan dari luar:

```bash
sudo ufw status verbose
sudo ss -tulpn | grep -E ':(22|80|443|3000|5432|8000)\b'
#  3000, 5432, 8000 harus berada di 127.0.0.1 saja

# dari komputer lain (bukan server):
nmap -Pn -p 22,80,443,3000,5432,8000 <IP_SERVER>
#  hanya 22, 80, 443 yang open
```

### 3.2 Header keamanan, penyembunyian versi, dan pembatasan login di Nginx (Rekomendasi)

Backend FastAPI hanya memasang CORS dan `X-Request-ID` (Aktual, `app/main.py`); header
keamanan dan pembatasan laju diletakkan di Nginx host.

```bash
sudo tee /etc/nginx/conf.d/wms-hardening.conf >/dev/null <<'EOF'
server_tokens off;
limit_req_zone $binary_remote_addr zone=wms_login:10m rate=20r/m;
limit_req_status 429;
EOF

sudo mkdir -p /etc/nginx/snippets
sudo tee /etc/nginx/snippets/wms-security-headers.conf >/dev/null <<'EOF'
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(self), microphone=(), geolocation=()" always;
# HSTS: mulai dengan umur pendek, naikkan setelah yakin HTTPS stabil.
add_header Strict-Transport-Security "max-age=300" always;
EOF
```

Lalu pada `/etc/nginx/sites-available/jejakstok.conf` (yang sudah diubah Certbot), di dalam
**setiap** blok `server` HTTPS tambahkan `include /etc/nginx/snippets/wms-security-headers.conf;`
dan di blok API tambahkan lokasi login sebelum `location /`:

```nginx
location = /api/v1/auth/login {
    limit_req zone=wms_login burst=10 nodelay;
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
}
```

`Permissions-Policy` mengizinkan kamera karena pemindai barcode kamera memakainya. Setelah
yakin, naikkan HSTS menjadi `max-age=31536000`. Jangan menambah `preload` tanpa pertimbangan
matang karena sulit dibatalkan.

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -sI https://api-jkstok.my.id/health | grep -iE '^(strict-transport|x-content-type|x-frame|server):'
# uji pembatasan (juga menghasilkan baris AUTH_LOGIN_FAILED di audit log; wajar):
for i in $(seq 1 40); do curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  https://api-jkstok.my.id/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"uji-rate-limit","password":"x"}'; done | sort | uniq -c
#  sebagian respons harus 429
```

### 3.3 TLS

Sertifikat Let's Encrypt dikelola Certbot dan diperbarui otomatis oleh timer systemd.
Pemeriksaan: `sudo certbot renew --dry-run` dan `systemctl list-timers | grep certbot`.

### 3.4 Alamat IP klien pada audit log (Rekomendasi)

Aplikasi hanya mempercayai `X-Forwarded-For` bila koneksi berasal dari alamat pada
`TRUSTED_PROXY_IPS` (Aktual, `app/api/deps.py`). Tanpa pengaturan ini, kolom
`audit_logs.ip_address` berisi alamat gateway Docker, bukan IP pengguna. Temukan gateway
jaringan compose lalu isi di `.env.production`:

```bash
docker network ls | grep wms
docker network inspect <nama_jaringan> --format '{{(index .IPAM.Config 0).Gateway}}'
# contoh isi: TRUSTED_PROXY_IPS=["172.18.0.1"]
```

Perubahan ini akan dimanfaatkan penuh pada Tahap 14 (penyempurnaan audit log).

## 4. Database dan koneksi antar-service

| Kontrol | Tujuan | Status |
| --- | --- | --- |
| Port PostgreSQL hanya di `127.0.0.1`; jaringan internal `wms_internal` | Database tidak terjangkau dari internet | Aktual (compose production) |
| Akses administrasi lewat SSH tunnel (DBeaver) | Tanpa membuka port database | Aktual (§11.C deployment) |
| Trigger append-only pada `audit_logs` dan `stock_movements` | Jejak tidak dapat diubah lewat aplikasi | Aktual (`007_append_only_guards.sql`) |
| Runtime memakai role `wms_app`, migrasi memakai `wms_owner` | Prinsip hak akses minimum | **Rekomendasi** (lihat §4.1) |

### 4.1 Pisahkan role runtime dan migrasi di production (Rekomendasi)

Konfigurasi production yang terdokumentasi memakai role pemilik (`wms_owner`) untuk
`DATABASE_URL` dan `MIGRATION_DATABASE_URL`. Role `wms_app` (tanpa `UPDATE/DELETE/TRUNCATE`
pada `audit_logs` dan `stock_movements`, tanpa hak DDL) dirancang untuk runtime, tetapi
`db/init/001_create_app_role.sql` hanya berjalan pada inisialisasi cluster kosong sehingga role
tersebut mungkin belum ada di production. Dengan role pemilik, kerentanan injeksi atau
kebocoran kredensial runtime dapat menonaktifkan trigger append-only (`ALTER TABLE ... DISABLE TRIGGER`).

Rancangan langkah (uji dulu di server development, lalu jalankan di production dengan
jendela pemeliharaan):

```sql
-- sebagai wms_owner; ganti <password_wms_app> dengan password acak baru
CREATE ROLE wms_app WITH LOGIN PASSWORD '<password_wms_app>' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE <nama_db> TO wms_app;
GRANT USAGE ON SCHEMA public TO wms_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO wms_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO wms_app;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE stock_movements, audit_logs FROM wms_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE schema_migrations FROM wms_app;
-- migrasi masa depan oleh wms_owner otomatis memberi hak CRUD pada tabel baru:
ALTER DEFAULT PRIVILEGES FOR ROLE wms_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wms_app;
ALTER DEFAULT PRIVILEGES FOR ROLE wms_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO wms_app;
```

Setelah itu ubah `DATABASE_URL` di `.env.production` agar memakai `wms_app`, sementara
`MIGRATION_DATABASE_URL` tetap `wms_owner`, lalu terapkan ulang container dan uji login serta
satu transaksi penuh (buat PO, terima barang). Catatan: tabel baru yang harus append-only
tetap perlu `REVOKE` eksplisit pada migrasinya.

## 5. Pengelolaan credential, token, dan environment variable

| Kontrol | Tujuan | Status |
| --- | --- | --- |
| `.env*` aktif ter-ignore Git; hanya `*.example` yang di-commit | Rahasia tidak masuk repositori | Aktual (`.gitignore` kedua repositori) |
| `.env.production` berizin `600`, milik `deployer`, tidak di Git | Membatasi pembacaan lokal | Jalankan di server |
| Secret CI/CD hanya di GitHub Secrets | Tidak ada rahasia di workflow | Aktual (§7.1 deployment) |
| `JWT_SECRET` dan password berbeda untuk tiap lingkungan | Kebocoran satu lingkungan tidak menjalar | Aktual (aturan di panduan environment) |
| Guard startup `APP_ENV=production` | Menolak `COOKIE_SECURE=False` dan `JWT_SECRET` placeholder | Aktual (`app/core/config.py`, diuji `tests/test_config_environment.py`) |
| Dokumen tidak memuat nilai asli | Mencegah kebocoran seperti pada §1 | Aktual (Documentation Standards) |

Tindakan di server: tambahkan `APP_ENV=production` ke `/opt/wms/.env.production` agar guard
aktif dan label lingkungan benar.

```bash
stat -c '%a %U:%G %n' /opt/wms/.env.production      # harus: 600 deployer:deployer
sudo chmod 600 /opt/wms/.env.production && sudo chown deployer:deployer /opt/wms/.env.production
```

Pemeriksaan kebocoran pada repositori (jalankan berkala atau sebagai pre-commit):

```bash
# memindai seluruh riwayat Git; instal gitleaks lebih dulu
gitleaks detect --source . --log-opts="--all" --redact
```

Jadwal rotasi yang disarankan: `JWT_SECRET` dan password database setiap 6 bulan atau segera
saat ada dugaan kebocoran atau pergantian personel; kunci SSH CI/CD saat personel berganti;
`CR_PAT` sesuai masa berlaku token.

## 6. Hak akses dan autentikasi pengguna (Aktual di kode)

| Kontrol | Implementasi | Pemeriksaan |
| --- | --- | --- |
| Hash password | Argon2id ([security.py](../../app/core/security.py)) | Kolom `password_hash` berformat `$argon2id$...` |
| Access token | JWT HS256, umur 15 menit, disimpan di memori klien | `ACCESS_TOKEN_MINUTES` |
| Refresh token | String acak opak, disimpan ter-hash SHA-256, umur 7 hari, rotasi, deteksi penggunaan ulang mencabut seluruh sesi | `tests/test_auth.py` (AC-11) |
| Cookie refresh | `HttpOnly`, `Secure`, `SameSite`, path `/api/v1/auth` | `Set-Cookie` pada respons login |
| Penguncian akun | 5 kali gagal berturut-turut mengunci 15 menit | `tests/test_auth.py` |
| RBAC dan warehouse scoping | Permission per endpoint dan cakupan gudang | `tests/test_rbac_scoping.py` (AC-05, AC-12) |
| CORS | Whitelist origin eksplisit dengan `allow_credentials`, tanpa wildcard | `FRONTEND_ORIGINS` |
| Audit | Append-only dengan trigger; atribut sensitif disaring dari `old_values`/`new_values` | `tests/test_immutability.py`, AC-08, AC-22 |

Batasan yang perlu diketahui:

- HS256 bersifat simetris; siapa pun yang memegang `JWT_SECRET` dapat memalsukan token. Itu
  sebabnya §1 mewajibkan rotasi.
- Tidak ada pembatasan laju di tingkat aplikasi selain penguncian akun; ditutup oleh Nginx (§3.2).
- Tidak ada pemeriksaan header `Origin`/`Referer` pada endpoint berbasis cookie. Pada
  production cookie memakai `SameSite=none` (lintas domain), sehingga `POST /auth/refresh` dan
  `POST /auth/logout` dapat dipicu dari situs lain. Penyerang tidak dapat membaca hasilnya
  (dibatasi CORS), tetapi dapat memaksa logout. **Rekomendasi:** tolak permintaan cookie
  dengan `Origin` di luar `FRONTEND_ORIGINS`.

## 7. Perlindungan terhadap celah aplikasi

| Ancaman | Kontrol yang ada | Pemeriksaan | Status |
| --- | --- | --- | --- |
| Injeksi SQL | Query berparameter `psycopg` tanpa ORM; klausa `WHERE` disusun dari fragmen tetap dengan nilai terikat; kolom urut dibatasi whitelist (AC-16) | `rg 'f"""?[^"]*(SELECT\|INSERT\|UPDATE\|DELETE)' app/` hanya boleh menemukan perakitan fragmen tetap | Aktual (pemindaian 2026-11-13: 20 perakitan `WHERE` dari fragmen tetap pada repository) |
| XSS | React meng-escape keluaran; tidak ada `dangerouslySetInnerHTML`/`innerHTML` pada `src/` | `rg 'dangerouslySetInnerHTML\|innerHTML' src` harus kosong | Aktual |
| Brute-force login | Penguncian akun + pembatasan Nginx | §3.2 | Aktual + Rekomendasi |
| Pencurian token | Access token di memori, refresh token `HttpOnly` | Tidak ada token di `localStorage` | Aktual |
| Kerentanan dependensi | Belum ada pemindaian otomatis | `pip-audit -r requirements.txt` dan `npm audit --omit=dev`; aktifkan Dependabot | Rekomendasi |
| Container | Backend berjalan sebagai `wmsuser` (bukan root) | `docker exec wms_prod_backend id` | Aktual |
| Kebocoran informasi error | Handler `Exception` mengembalikan `INTERNAL_ERROR` tanpa detail teknis | AC-17, `app/main.py` | Aktual |

## 8. Backup dan recovery

Target: **RPO 24 jam** (cadangan harian) dan **RTO 2 jam**. Sesuaikan jika kebutuhan bisnis
berbeda. Cadangan yang belum pernah diuji pemulihannya dianggap belum ada.

### 8.1 Skrip cadangan harian (Jalankan di server)

Skrip membaca nama database dan pengguna dari `.env.production` dengan `grep` (bukan
`source`, agar karakter khusus pada password tidak merusak parsing), menulis ke berkas
sementara, memverifikasi isinya, lalu memutar cadangan lama.

```bash
sudo -u deployer tee /opt/wms/backup-db.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ENV_FILE=/opt/wms/.env.production
BACKUP_DIR=/opt/wms/backups
RETENTION_DAYS=14
DB_USER=$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)
DB_NAME=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)
STAMP=$(date +%F_%H%M%S)
TMP="$BACKUP_DIR/.tmp_${STAMP}.dump"
OUT="$BACKUP_DIR/wms_${DB_NAME}_${STAMP}.dump"

umask 077
docker exec wms_prod_postgres pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$TMP"
# verifikasi: berkas tidak kosong dan dapat dibaca pg_restore
test -s "$TMP"
docker exec -i wms_prod_postgres pg_restore --list < "$TMP" >/dev/null
mv "$TMP" "$OUT"
find "$BACKUP_DIR" -name 'wms_*.dump' -mtime +"$RETENTION_DAYS" -delete
echo "$(date -Is) backup ok: $OUT ($(du -h "$OUT" | cut -f1))"
EOF
chmod 700 /opt/wms/backup-db.sh
/opt/wms/backup-db.sh                       # uji manual sekali

# jadwalkan 02:00 setiap hari sebagai deployer
( crontab -l 2>/dev/null; echo '0 2 * * * /opt/wms/backup-db.sh >> /opt/wms/backups/backup.log 2>&1' ) | crontab -
```

Cadangan di disk server yang sama tidak melindungi dari kegagalan disk atau server.
**Rekomendasi:** salin ke lokasi lain secara terenkripsi (mis. `rclone` ke penyimpanan objek
atau `scp` ke server kedua) dan simpan salinan `.env.production` secara terpisah serta
terenkripsi, karena tanpa itu database tidak dapat dioperasikan setelah pemulihan.

### 8.2 Uji pemulihan (lakukan bulanan)

Pulihkan ke database sementara, **bukan** ke database aktif:

```bash
LATEST=$(ls -1t /opt/wms/backups/wms_*.dump | head -1)
DB_USER=$(grep -E '^POSTGRES_USER=' /opt/wms/.env.production | cut -d= -f2-)
docker exec wms_prod_postgres createdb -U "$DB_USER" wms_restore_test
docker exec -i wms_prod_postgres pg_restore -U "$DB_USER" -d wms_restore_test --no-owner < "$LATEST"
docker exec wms_prod_postgres psql -U "$DB_USER" -d wms_restore_test -c \
  "SELECT (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM audit_logs) AS audit_logs, (SELECT max(version) FROM schema_migrations) AS versi_migrasi;"
docker exec wms_prod_postgres dropdb -U "$DB_USER" wms_restore_test
```

Hasil diterima bila jumlah baris masuk akal dibanding produksi dan `versi_migrasi` sesuai
migrasi terakhir yang diterapkan. Catat tanggal, berkas, dan hasil uji.

### 8.3 Pemulihan penuh saat bencana

1. Hentikan aplikasi: `docker compose -f docker-compose.prod.yml stop backend frontend`.
2. Buat cadangan kondisi saat ini terlebih dulu (walau rusak) untuk bahan investigasi.
3. Pulihkan: `docker exec -i wms_prod_postgres pg_restore -U <user> -d <db> --clean --if-exists --no-owner < <berkas.dump>`.
4. Jalankan migrasi (`backend-migration`), nyalakan backend, lalu frontend.
5. Verifikasi `/health`, login, dan saldo stok pada beberapa gudang terhadap catatan terakhir.

## 9. Monitoring aktivitas dan keamanan

Notifikasi otomatis (error aplikasi dan status container lewat Telegram) dikerjakan pada
Tahap 13; sebelum itu gunakan pemeriksaan manual berikut.

| Frekuensi | Pemeriksaan | Perintah | Normal bila |
| --- | --- | --- | --- |
| Harian | Percobaan login SSH gagal | `sudo journalctl -u ssh --since yesterday \| grep -c 'Failed password\|Invalid user'` | Rendah/menurun setelah `fail2ban` aktif |
| Harian | IP terblokir | `sudo fail2ban-client status sshd` | Jail aktif |
| Harian | Status container | `docker ps --format 'table {{.Names}}\t{{.Status}}'` | Semua `Up`, `healthy` bila ada healthcheck |
| Harian | Cadangan terbaru | `tail -n 3 /opt/wms/backups/backup.log` | Baris `backup ok` tanggal hari ini |
| Harian | Lonjakan galat/serangan | `sudo awk '{print $9}' /var/log/nginx/access.log \| sort \| uniq -c \| sort -rn \| head` | Proporsi 401/404/429/5xx kecil |
| Mingguan | Aktivitas autentikasi mencurigakan | SQL di bawah | Tanpa lonjakan `AUTH_LOGIN_LOCKED` atau `AUTH_REFRESH_TOKEN_REUSE_DETECTED` |
| Mingguan | Port terbuka | `sudo ss -tulpn` | Sesuai §3.1 |
| Mingguan | Pembaruan OS | `apt list --upgradable 2>/dev/null \| head` dan `ls /var/run/reboot-required` | Tidak ada pembaruan keamanan tertunda |
| Mingguan | Kapasitas | `df -h /` dan `docker system df` | Disk di bawah 80% |
| Bulanan | Uji pemulihan, rotasi kunci yang jatuh tempo, tinjau akun admin | §8.2 | Tercatat |

```sql
SELECT action, count(*) AS jumlah, count(DISTINCT ip_address) AS ip_berbeda, max(created_at) AS terakhir
FROM audit_logs
WHERE created_at >= now() - interval '7 days'
  AND action IN ('AUTH_LOGIN_FAILED','AUTH_LOGIN_LOCKED','AUTH_REFRESH_TOKEN_REUSE_DETECTED','AUTH_TOKEN_REFRESH_FAILED')
GROUP BY action ORDER BY jumlah DESC;
```

## 10. Checklist verifikasi akhir

Centang setelah dijalankan di server, lalu catat tanggalnya.

- [ ] Rahasia pada §1 sudah dirotasi (JWT, password `wms_owner`) dan login berfungsi
- [ ] `APP_ENV=production` aktif dan aplikasi start normal
- [ ] `sshd -T` menunjukkan `passwordauthentication no` dan `permitrootlogin no`
- [ ] `fail2ban-client status sshd` aktif; `ufw status` menunjukkan SSH `LIMIT`
- [ ] `nmap` dari luar hanya menemukan port 22, 80, 443
- [ ] Header keamanan tampil pada `curl -I` dan login mengembalikan 429 saat dibanjiri
- [ ] `TRUSTED_PROXY_IPS` diisi dan `audit_logs.ip_address` berisi IP pengguna asli
- [ ] `.env.production` berizin 600
- [ ] Cadangan terjadwal berjalan dan satu uji pemulihan berhasil
- [ ] GitHub secret scanning dan push protection aktif
- [ ] Keputusan tentang pemisahan role `wms_app` (§4.1) dan pemeriksaan `Origin` (§6) dicatat
