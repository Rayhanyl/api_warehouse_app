# Panduan Deployment Production & Otomasi CI/CD — JejakStok WMS

Dokumen ini merupakan panduan resmi standar operasional prosedur (SOP) deployment JejakStok WMS ke server production dengan menerapkan **Continuous Integration / Continuous Deployment (CI/CD)** menggunakan **GitHub Actions** dan **Container Registry (GitHub Packages / GHCR)**.

---

## 1. Prinsip Utama & Arsitektur Deployment

Deployment JejakStok menerapkan prinsip **Immutable Infrastructure & Remote Build**:
1. **Server Production Bersih dari Build Tools**: Server production **tidak pernah melakukan kompilasi atau build kode** (tidak ada `npm run build`, `tsc`, `pip install`, atau `docker build` di server).
2. **Build Terpusat di GitHub Actions**: Seluruh proses kompilasi TypeScript, pengujian otomatis, pembuatan Docker image, dan tagging dilakukan sepenuhnya di runner GitHub Actions.
3. **Container Registry sebagai Single Source of Truth**: Docker image yang telah lulus pengujian diunggah ke GitHub Container Registry (`ghcr.io`).
4. **Server Hanya Melakukan Pull & Run**: Server production hanya bertugas mengunduh (*pull*) image siap pakai dari registry dan me-restart container menggunakan Docker Compose.

```mermaid
flowchart TD
    subgraph Developer Workflow
        DEV[Developer Local] -->|Push kode| BR_DEV[Branch development]
        BR_DEV -->|Buat Pull Request| PR[Pull Request: development -> main]
    end

    subgraph GitHub Quality Gate
        PR -->|Trigger Otomatis| CI[GitHub Actions CI: Pytest & Vitest]
        CI -->|Status Lolos & Hijau| REV[Code Review & Approval Minimal 1 Reviewer]
        REV -->|Disetujui| MERGE[Merge PR ke branch main]
    end

    subgraph GitHub Actions CD Pipeline
        MERGE -->|Trigger Push ke main| CD[GitHub Actions CD Pipeline]
        CD -->|Build Docker Multi-Stage| DOCKER_BUILD[Build Image Backend & Frontend]
        DOCKER_BUILD -->|Tagging: SHA & latest| GHCR[Push Image ke ghcr.io]
        GHCR -->|Trigger Deployment via SSH| SSH_DEPLOY[SSH ke Server Production]
    end

    subgraph Production Server
        SSH_DEPLOY -->|docker compose pull| PULL[Pull Image Terbaru dari ghcr.io]
        PULL -->|Jalankan Migrasi DB| MIGRATE[python -m db.migrate]
        MIGRATE -->|Zero/Minimal Downtime| RESTART[docker compose up -d]
        RESTART -->|Cek /health| VERIFY[Verifikasi Healthcheck Berhasil]
    end
```

---

## 2. Alur Workflow Git & Aturan Branching

### 2.1 Struktur Branch
- **`development`**: Branch kerja aktif utama. Seluruh fitur baru, perbaikan bug, dan integrasi antar-developer di-push ke branch ini.
- **`main`**: Branch rilis produksi. Kode di branch `main` harus selalu berada dalam kondisi stabil, telah diuji, dan siap berjalan di server production.

### 2.2 Aturan Ketat Branch `main` (Branch Protection Rules)
Untuk menjamin stabilitas production, branch `main` wajib dilindungi melalui pengaturan GitHub (**Settings -> Branches -> Branch protection rules**):
1. **Require a pull request before merging**:
   - Dilarang melakukan *direct push* (`git push origin main` ditolak oleh sistem).
   - Setiap perubahan harus melalui Pull Request dari branch `development`.
2. **Require approvals**:
   - Minimal **1 reviewer** (Tech Lead / Peer Developer) harus memberikan status *Approved* sebelum tombol merge aktif.
3. **Require status checks to pass before merging**:
   - Seluruh pemeriksaan CI (Backend pytest, Frontend vitest & typecheck) wajib berstatus **HIJAU (Passed)**.
4. **Require branches to be up to date before merging**:
   - Menghindari konflik tersembunyi dengan memastikan branch PR telah mengintegrasikan commit terbaru.
5. **Do not allow bypassing the above settings**:
   - Berlaku untuk seluruh pengguna, termasuk akun Repository Administrator.

---

## 3. SOP Pembuatan Pull Request, Code Review, & Merge

```text
[development] ──(PR Baru)──> [Validasi CI Hijau] ──(Review & Approve)──> [Merge ke main] ──(Auto Deploy)
```

### Langkah 1: Developer Mempersiapkan Perubahan
Pastikan seluruh pengujian lokal telah lulus sebelum membuat PR:
```bash
# Di terminal backend
cd api_warehouse_app
pytest

# Di terminal frontend
cd ../warehouse_app
npx vitest run
npm run build
```

### Langkah 2: Membuat Pull Request ke Branch `main`
1. Buka repositori di GitHub.
2. Navigasi ke tab **Pull requests -> New pull request**.
3. Pilih **base: `main`** dan **compare: `development`**.
4. Isi judul dan deskripsi PR mengikuti template berikut:
   ```markdown
   ## Ringkasan Perubahan
   - [Fitur/Bugfix] Penjelasan singkat perubahan yang dilakukan.
   - [AC Terkait] Menyebutkan acceptance criteria yang terpenuhi (misal: AC-38).

   ## Checklist Developer
   - [x] Kode telah diuji secara lokal (pytest & vitest lulus 100%).
   - [x] Tidak ada breaking changes pada skema database yang belum dimigrasikan.
   - [x] Tidak menyimpan rahasia/secret/token ke dalam kode git.
   - [x] Dokumentasi terkait (PRD / API Contract) telah diperbarui.
   ```

### Langkah 3: Code Review & Persetujuan
- Reviewer memeriksa *Files changed* untuk memastikan:
  - Arsitektur lapisan tetap dipatuhi (`routes -> services -> repositories`).
  - Aturan keamanan (SQL berparameter, password hashing, no sensitive data di log) tidak dilanggar.
- Jika ada catatan, diskusikan melalui fitur komentar GitHub.
- Jika sudah sesuai, Reviewer menekan tombol **Review changes -> Approve**.

### Langkah 4: Merge ke Branch `main`
- Pilih metode **Squash and merge** atau **Rebase and merge** untuk menjaga riwayat commit branch `main` tetap bersih dan linear.
- Konfirmasi merge. Aksi ini secara otomatis memicu GitHub Actions CD Pipeline.

---

## 4. Konfigurasi CI/CD Pipeline (GitHub Actions)

Workflow GitHub Actions dibagi menjadi 2 pipeline terpisah pada direktori `.github/workflows/`:

### 4.1 Pipeline CI: Verifikasi Otomatis PR (`.github/workflows/ci.yml`)
Workflow ini otomatis berjalan saat ada **Pull Request ke branch `main`** atau **Push ke branch `development`**.

```yaml
name: Continuous Integration (CI)

on:
  pull_request:
    branches: [main]
  push:
    branches: [development]

jobs:
  backend-test:
    name: Backend Test (pytest)
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: wms_owner
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: wms_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout Kode
        uses: actions/checkout@v4

      - name: Setup Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install Dependensi Backend
        run: |
          cd api_warehouse_app
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest httpx

      - name: Jalankan Migrasi & Pytest
        env:
          DATABASE_URL: postgresql://wms_owner:test_password@localhost:5432/wms_test
          MIGRATION_DATABASE_URL: postgresql://wms_owner:test_password@localhost:5432/wms_test
          TEST_DATABASE_URL: postgresql://wms_owner:test_password@localhost:5432/wms_test
          JWT_SECRET: ci-secret-key-must-be-at-least-32-bytes-long
        run: |
          cd api_warehouse_app
          python -m db.migrate
          pytest -v

  frontend-test:
    name: Frontend Test & Build (vitest & tsc)
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Kode
        uses: actions/checkout@v4

      - name: Setup Node.js 22
        uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: "npm"
          cache-dependency-path: warehouse_app/package-lock.json

      - name: Install Dependensi Frontend
        run: |
          cd warehouse_app
          npm ci

      - name: Jalankan Vitest Suite
        run: |
          cd warehouse_app
          npx vitest run

      - name: Uji Typecheck & Build Produksi
        run: |
          cd warehouse_app
          npm run build
```

---

### 4.2 Pipeline CD: Build Docker & Deploy ke Server (`.github/workflows/deploy.yml`)
Workflow ini otomatis berjalan **hanya ketika ada commit masuk ke branch `main`** (hasil merge PR).

```yaml
name: Continuous Deployment (CD)

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  BACKEND_IMAGE_NAME: ${{ github.repository }}/wms-backend
  FRONTEND_IMAGE_NAME: ${{ github.repository }}/wms-frontend

jobs:
  build-and-push:
    name: Build Docker Images & Push to GHCR
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout Kode
        uses: actions/checkout@v4

      - name: Setup Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login ke GitHub Container Registry (GHCR)
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Ekstrak Metadata & Tagging Docker
        id: meta-backend
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.BACKEND_IMAGE_NAME }}
          tags: |
            type=raw,value=latest
            type=sha,format=short,prefix=sha-

      - name: Build & Push Backend Image
        uses: docker/build-push-action@v5
        with:
          context: ./api_warehouse_app
          file: ./api_warehouse_app/Dockerfile
          push: true
          tags: ${{ steps.meta-backend.outputs.tags }}
          labels: ${{ steps.meta-backend.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Ekstrak Metadata Frontend
        id: meta-frontend
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.FRONTEND_IMAGE_NAME }}
          tags: |
            type=raw,value=latest
            type=sha,format=short,prefix=sha-

      - name: Build & Push Frontend Image
        uses: docker/build-push-action@v5
        with:
          context: ./warehouse_app
          file: ./warehouse_app/Dockerfile
          build-args: |
            VITE_API_BASE_URL=https://api-jkstok.my.id
          push: true
          tags: ${{ steps.meta-frontend.outputs.tags }}
          labels: ${{ steps.meta-frontend.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-to-server:
    name: Deploy Container to Production Server
    needs: build-and-push
    runs-on: ubuntu-latest

    steps:
      - name: Eksekusi Deployment via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.PROD_SERVER_HOST }}
          username: ${{ secrets.PROD_SERVER_USER }}
          key: ${{ secrets.PROD_SERVER_SSH_KEY }}
          port: ${{ secrets.PROD_SERVER_PORT || 22 }}
          script_stop: true
          script: |
            set -e
            echo "=== Memulai Proses Deployment JejakStok WMS ==="
            cd /opt/wms

            echo "1. Login ke Container Registry..."
            echo "${{ secrets.CR_PAT }}" | docker login ghcr.io -u "${{ github.actor }}" --password-stdin

            echo "2. Menarik Image Terbaru (Pull)..."
            docker compose -f docker-compose.prod.yml pull

            echo "3. Menjalankan Migrasi Database..."
            docker compose -f docker-compose.prod.yml run --rm backend-migration

            echo "4. Menjalankan Container Baru (Rolling Update)..."
            docker compose -f docker-compose.prod.yml up -d --remove-orphans

            echo "5. Verifikasi Status Container..."
            docker compose -f docker-compose.prod.yml ps

            echo "6. Pembersihan Image Gantung (Prune)..."
            docker image prune -af --filter "until=72h"

            echo "=== Deployment Selesai dengan Sukses ==="
```

---

## 5. Dockerfile Produksi

### 5.1 Dockerfile Backend (`api_warehouse_app/Dockerfile`)
Menggunakan user non-root dan Python slim image untuk keamanan serta efisiensi ukuran:
```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY db ./db
COPY scripts ./scripts

RUN useradd --create-home --shell /bin/bash wmsuser \
    && chown -R wmsuser:wmsuser /app

USER wmsuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 5.2 Dockerfile Frontend (`warehouse_app/Dockerfile`)
Menggunakan **Multi-Stage Build**: Node.js hanya digunakan pada tahap build aset statis, lalu hasil kompilasi disajikan oleh Nginx Alpine berukuran sangat kecil (~25 MB):
```dockerfile
# Stage 1: Build Aset
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve dengan Nginx
FROM nginx:1.27-alpine

# Salin konfigurasi Nginx SPA
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Salin hasil build dari stage builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

Konfigurasi Nginx SPA (`warehouse_app/nginx.conf`):
```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Gzip Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript image/svg+xml;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API ke Backend Container
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 6. Persiapan Server Production & Konfigurasi Host

### 6.1 Paket yang Wajib Di-install di Server Production
Server production menggunakan sistem operasi **Ubuntu 22.04 LTS atau Ubuntu 24.04 LTS**. Sesuai prinsip **Zero Build**, server hanya bertugas menjalankan container siap pakai sehingga **TIDAK PERLU** menginstal Node.js, npm, Python, pip, GCC, atau build tools lainnya.

Jalankan perintah berikut di server (sebagai user dengan akses `sudo`):

```bash
# 1. Update repository dan instalasi paket utilitas sistem dasar
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl ufw apt-transport-https ca-certificates gnupg lsb-release

# 2. Instalasi Docker Engine & Docker Compose Plugin dari Repository Resmi Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 3. Instalasi Nginx (Host Reverse Proxy) & Certbot Let's Encrypt (SSL)
sudo apt install -y nginx certbot python3-certbot-nginx

# 4. Konfigurasi Firewall (UFW)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full' # Membuka port 80 (HTTP) dan port 443 (HTTPS)
sudo ufw --force enable
```

### 6.2 Setup Pengguna Deployment & Direktori Kerja
Buat pengguna non-root khusus deployment (`deployer`) dan izinkan menjalankan Docker tanpa `sudo`:

```bash
# Buat user deployer dan tambahkan ke grup docker
sudo adduser --gecos "" deployer
sudo usermod -aG docker deployer

# Siapkan SSH authorized_keys untuk autentikasi GitHub Actions
sudo mkdir -p /home/deployer/.ssh
sudo cp ~/.ssh/authorized_keys /home/deployer/.ssh/ # Atau salin public key GitHub Actions
sudo chown -R deployer:deployer /home/deployer/.ssh
sudo chmod 700 /home/deployer/.ssh
sudo chmod 600 /home/deployer/.ssh/authorized_keys

# Siapkan direktori aplikasi /opt/wms
sudo mkdir -p /opt/wms/backups
sudo chown -R deployer:deployer /opt/wms
```

### 6.3 Struktur Direktori di Server (`/opt/wms/`)
```text
/opt/wms/
├── docker-compose.prod.yml   # Definisi container production
├── .env.production           # Environment variables rahasia (chmod 600)
└── backups/                  # Direktori backup dump database harian
```

### 6.4 Docker Compose Production (`/opt/wms/docker-compose.prod.yml`)
> **PENTING**: File ini **TIDAK memiliki direktif `build:`**. Seluruh image di-pull langsung dari GHCR registry.

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: wms_prod_postgres
    restart: always
    env_file: .env.production
    volumes:
      - postgres_prod_data:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432" # Akses aman lokal via SSH Tunnel (untuk DBeaver / pgAdmin)
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - wms_internal

  backend-migration:
    image: ghcr.io/rayhanyl/api_warehouse_app/wms-backend:latest
    container_name: wms_prod_migration
    restart: "no"
    env_file: .env.production
    depends_on:
      postgres:
        condition: service_healthy
    command: ["python", "-m", "db.migrate"]
    networks:
      - wms_internal

  backend:
    image: ghcr.io/rayhanyl/api_warehouse_app/wms-backend:latest
    container_name: wms_prod_backend
    restart: always
    env_file: .env.production
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "127.0.0.1:8000:8000"
    networks:
      - wms_internal

  frontend:
    image: ghcr.io/rayhanyl/warehouse_app/wms-frontend:latest
    container_name: wms_prod_frontend
    restart: always
    depends_on:
      backend:
        condition: service_healthy
    ports:
      - "127.0.0.1:3000:80"
    networks:
      - wms_internal

volumes:
  postgres_prod_data:

networks:
  wms_internal:
    driver: bridge
```

### 6.5 Konfigurasi Host Reverse Proxy Nginx & Sertifikat SSL
Host Nginx bertugas menerima traffic HTTPS dari internet publik dan meneruskannya ke port internal container Docker (`127.0.0.1:8000` untuk Backend dan `127.0.0.1:3000` untuk Frontend).

Buat file konfigurasi di `/etc/nginx/sites-available/jejakstok.conf`:

```nginx
# ==============================================================================
# 1. Virtual Host untuk Backend API (api-jkstok.my.id)
# ==============================================================================
server {
    listen 80;
    server_name api-jkstok.my.id;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https; # Krusial: Beritahu FastAPI bahwa request berasal dari HTTPS

        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}

# ==============================================================================
# 2. Virtual Host untuk Frontend Web (jejakstok.site)
# ==============================================================================
server {
    listen 80;
    server_name jejakstok.site www.jejakstok.site;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

Aktifkan konfigurasi Nginx dan pasang sertifikat SSL Let's Encrypt gratis:
```bash
# Aktifkan virtual host
sudo ln -s /etc/nginx/sites-available/jejakstok.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Dapatkan sertifikat SSL otomatis melalui Certbot
sudo certbot --nginx -d api-jkstok.my.id -d jejakstok.site -d www.jejakstok.site
```
> **Catatan DNS**: Pastikan A-Record DNS `api-jkstok.my.id` dan `jejakstok.site` di dashboard penyedia domain Anda sudah mengarah ke IP Publik server sebelum menjalankan Certbot.

---

## 7. Pengelolaan Environment Variables & GitHub Settings

### 7.1 Pengaturan di Repositori GitHub

#### A. Branch Protection Rules (Wajib)
Masuk ke menu **Settings -> Branches -> Add branch protection rule**:
1. **Branch name pattern**: `main`
2. Centang **Require a pull request before merging**:
   - Required approvals: `1`
   - Centang *Dismiss stale pull request approvals when new commits are pushed*
3. Centang **Require status checks to pass before merging**:
   - Status checks yang wajib lolos: `Backend Test (pytest)` dan `Frontend Test & Build (vitest & tsc)`
4. Centang **Require branches to be up to date before merging**
5. Centang **Do not allow bypassing the above settings** (berlaku untuk admin repository)

#### B. GitHub Actions Secrets
Daftarkan rahasia berikut pada repository GitHub (**Settings -> Secrets and variables -> Actions -> Repository secrets**):

| Nama Secret | Deskripsi / Nilai Riil di Server Production |
| :--- | :--- |
| `PROD_SERVER_HOST` | `<IP_PUBLIK_SERVER_PROD>` (IP Publik server VPS, contoh: `203.0.113.10`) |
| `PROD_SERVER_USER` | `deployer` (User deployment khusus di server) |
| `PROD_SERVER_PORT` | `22` (Port SSH server default) |
| `PROD_SERVER_SSH_KEY` | Private SSH Key ed25519 (tersimpan di server pada `/home/deployer/.ssh/id_ed25519_github_actions`) |
| `CR_PAT` | GitHub Personal Access Token (Classic) dengan scope `read:packages` untuk login GHCR |

#### C. Pengaturan Visibilitas Package GHCR
Buka tab **Packages** di profil GitHub / Organisasi:
- Cari package `wms-backend` dan `wms-frontend`.
- Masuk ke **Package settings**:
  - Jika diset **Private**: Server wajib login menggunakan `CR_PAT` (sudah otomatis ditangani di CD pipeline).
  - Jika diset **Public**: Server dapat melakukan `docker pull` tanpa kredensial.

---

### 7.2 File `.env.production` di Server (`/opt/wms/.env.production`)
File ini disimpan langsung di server pada `/opt/wms/.env.production` dan dilindungi dengan izin akses ketat:
```bash
chmod 600 /opt/wms/.env.production
```

Isi konfigurasi riil `/opt/wms/.env.production`:
```env
# ==============================================================================
# Database Credentials & Connection Strings (Gunakan password acak kuat minimal 32 karakter)
# ==============================================================================
POSTGRES_USER=wms_owner
POSTGRES_PASSWORD=<GANTI_DENGAN_PASSWORD_DB_PRODUKSI_YANG_KUAT>
POSTGRES_DB=wms_production

# URL koneksi untuk runtime FastAPI & migrasi database
DATABASE_URL=postgresql://wms_owner:<GANTI_DENGAN_PASSWORD_DB_PRODUKSI_YANG_KUAT>@postgres:5432/wms_production
MIGRATION_DATABASE_URL=postgresql://wms_owner:<GANTI_DENGAN_PASSWORD_DB_PRODUKSI_YANG_KUAT>@postgres:5432/wms_production

# ==============================================================================
# JWT & Keamanan Sesi (Generate via: openssl rand -hex 32)
# ==============================================================================
JWT_SECRET=<GANTI_DENGAN_RANDOM_SECRET_HEX_64_CHAR>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7

# ==============================================================================
# Konfigurasi Cross-Site Cookie & CORS (Domain Riil Produksi)
# ==============================================================================
COOKIE_SECURE=True
COOKIE_SAMESITE=none
FRONTEND_ORIGINS=["https://jejakstok.site", "https://www.jejakstok.site"]

# ==============================================================================
# Proteksi Brute-Force Login
# ==============================================================================
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15
```

> [!IMPORTANT]
> **Mengapa `COOKIE_SAMESITE=none` dan `COOKIE_SECURE=True` Wajib?**
> Domain Frontend (`https://jejakstok.site`) dan Backend API (`https://api-jkstok.my.id`) memiliki *effective Top-Level Domain* (eTLD+1) yang **berbeda** (`jejakstok.site` vs `jkstok.my.id`).
> Sesuai standar keamanan RFC 6265bis, browser memblokir pengiriman cookie `SameSite=Lax` pada request asinkron AJAX/Axios (`withCredentials: true`) lintas domain.
> Oleh karena itu, cookie `refresh_token` **wajib** menggunakan `SameSite=None` dan `Secure=True` (HTTPS). Jika tidak, sesi pengguna di frontend tidak akan bisa dipulihkan setelah reload halaman (*refresh token hilang*).

---

## 8. Strategi Rollback Cepat

Jika versi terbaru yang di-deploy mengalami bug kritis atau anomali:

### Metode 1: Rollback Melalui GitHub Git Revert (Rekomendasi)
1. Buka commit/PR bermasalah di GitHub.
2. Klik tombol **Revert**.
3. GitHub akan membuat PR pembalik ke branch `main`.
4. Merge PR revert tersebut. GitHub Actions CD Pipeline akan secara otomatis melakukan build ulang dari commit yang stabil dan men-deploy kembali ke server.

### Metode 2: Rollback Cepat Langsung di Server (Emergency Hot-Rollback)
Jika server harus segera dipulihkan dalam hitungan detik tanpa menunggu build pipeline:
1. Login ke server via SSH:
   ```bash
   ssh deployer@<IP_PUBLIK_SERVER_PROD>
   cd /opt/wms
   ```
2. Jalankan container dengan merujuk tag SHA commit sebelumnya yang stabil:
   ```bash
   # Ganti 'sha-xxxxxxx' dengan commit SHA versi stabil sebelumnya
   docker compose -f docker-compose.prod.yml down
   IMAGE_TAG=sha-abc1234 docker compose -f docker-compose.prod.yml up -d
   ```
3. Periksa status aplikasi:
   ```bash
   docker compose -f docker-compose.prod.yml ps
   curl -f http://127.0.0.1:8000/health
   ```

---

## 9. Checklist Audit & Best Practices Keamanan

- [x] **No Build in Prod**: Server production tidak memiliki compiler, npm, gcc, atau pip cache.
- [x] **Branch Protection Active**: Branch `main` terkunci dari direct push; wajib melalui PR dan approval.
- [x] **CI Green Requirement**: PR tidak dapat di-merge jika pengujian backend atau frontend gagal.
- [x] **Image Immutability**: Docker image diberi tag `sha-<commit>` di samping `latest` untuk penelusuran audit yang presisi.
- [x] **Non-Root User**: Container backend berjalan dengan user `wmsuser` (UID 1000), bukan `root`.
- [x] **Atomic DB Migrations**: Migrasi dijalankan sebagai task terisolasi (`backend-migration`) sebelum container utama menerima traffic.
- [x] **Healthcheck Verification**: Setiap service memiliki healthcheck native (`/health` pada backend, `wget` pada frontend).
- [x] **Strict Secret Permissions**: File `.env.production` berizin `600` dan tidak pernah dimasukkan ke version control git.

---

## 10. Panduan Operasional Docker & Pemeliharaan Server

### A. Perintah Rutin Operasional Docker Compose
Seluruh perintah operasional dijalankan di `/opt/wms`:

```bash
cd /opt/wms

# 1. Melihat status seluruh container beserta healthcheck
docker compose -f docker-compose.prod.yml ps

# 2. Melihat log real-time aplikasi backend
docker compose -f docker-compose.prod.yml logs -f backend

# 3. Melihat log database PostgreSQL
docker compose -f docker-compose.prod.yml logs -f postgres

# 4. Merestart container tertentu
docker compose -f docker-compose.prod.yml restart backend

# 5. Menerapkan ulang variabel environment baru (Force Recreate)
# PENTING: Jalankan perintah ini setiap kali Anda mengubah file .env.production!
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
```

### B. Monitoring Penggunaan Resource Server
```bash
# Pantau konsumsi CPU, Memory, dan I/O setiap container secara live
docker stats

# Periksa kapasitas disk yang digunakan oleh Docker
docker system df
```

### C. Pembersihan Image Kadaluarsa (Disk Cleanup)
Untuk mencegah disk VPS penuh akibat penumpukan image lama dari alur CI/CD:
```bash
# Hapus image dan container gantung yang tidak digunakan lebih dari 72 jam
docker image prune -af --filter "until=72h"
```

---

## 11. Manajemen Database, Backup & Akses DBeaver

### A. Backup Database Berkala
File cadangan disimpan otomatis di direktori `/opt/wms/backups/`:

```bash
# 1. Backup dump database SQL standar
docker exec wms_prod_postgres pg_dump -U wms_owner wms_production > /opt/wms/backups/backup_wms_$(date +%F_%H%M%S).sql

# 2. Backup dump terkompresi Gzip (menghemat disk space)
docker exec wms_prod_postgres pg_dump -U wms_owner wms_production | gzip > /opt/wms/backups/backup_wms_$(date +%F_%H%M%S).sql.gz
```

### B. Restore Database dari File Backup
```bash
cat /opt/wms/backups/nama_file_backup.sql | docker exec -i wms_prod_postgres psql -U wms_owner -d wms_production
```

### C. Akses Database Production via DBeaver (SSH Tunnel)
Database PostgreSQL aman dan dapat dikelola langsung via DBeaver tanpa membuka port 5432 ke internet:
1. **Tab Main**:
   * **Host**: `localhost` *(atau `127.0.0.1`)*
   * **Port**: `5432`
   * **Database**: `wms_production`
   * **Username**: `wms_owner`
   * **Password**: `<password_wms_owner_prod>`
2. **Tab SSH**:
   * Centang **Use SSH Tunnel**
   * **Host / IP**: `<IP_PUBLIK_SERVER_PROD>`
   * **Port**: `22`
   * **User name**: `ubuntu` *(atau `deployer`)*
   * **Auth**: Kunci SSH atau password SSH server Anda.
3. Klik **Test Connection** $\rightarrow$ Status **Connected** $\rightarrow$ Selesai.

---

## 12. Catatan Kritis Dependensi Backend (`requirements.txt`)

> [!WARNING]
> **Penting untuk Developer Backend:**
> Pada repositori GitHub (`Rayhanyl/api_warehouse_app`), pastikan dependensi berikut tercantum di `requirements.txt` dan disimpan dalam encoding **UTF-8**:
> ```text
> openpyxl>=3.1.0
> python-multipart>=0.0.9
> ```
> Modul `openpyxl` digunakan oleh `app/services/master_service.py` untuk parsing file Excel `.xlsx`. Jika dependensi ini tidak ada di `requirements.txt`, build GitHub Actions runner akan gagal saat aplikasi diinisialisasi.
