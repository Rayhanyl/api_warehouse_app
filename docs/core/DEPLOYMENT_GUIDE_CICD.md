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

## 6. Konfigurasi Server Production

### 6.1 Struktur Direktori di Server (`/opt/wms/`)
```text
/opt/wms/
├── docker-compose.prod.yml   # Definisi container production
├── .env.production           # Environment variables rahasia (chmod 600)
└── backups/                  # Direktori backup dump database harian
```

### 6.2 Docker Compose Production (`/opt/wms/docker-compose.prod.yml`)
> **PENTING**: File ini **TIDAK memiliki direktif `build:`**. Seluruh image di-pull langsung dari registry.

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
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - wms_internal

  backend-migration:
    image: ghcr.io/<ORGANISASI>/wms-backend:latest
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
    image: ghcr.io/<ORGANISASI>/wms-backend:latest
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
    image: ghcr.io/<ORGANISASI>/wms-frontend:latest
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

---

## 7. Pengelolaan Environment Variables & GitHub Secrets

### 7.1 GitHub Repository Secrets
Daftarkan secrets berikut pada repository GitHub (**Settings -> Secrets and variables -> Actions**):

| Nama Secret | Deskripsi / Contoh Nilai |
| --- | --- |
| `PROD_SERVER_HOST` | Alamat IP Publik atau domain server production (misal: `203.0.113.10`) |
| `PROD_SERVER_USER` | Username SSH untuk deployment (misal: `deployer` / `ubuntu`) |
| `PROD_SERVER_SSH_KEY` | Private SSH Key (ed25519/rsa) milik server |
| `PROD_SERVER_PORT` | Port SSH server (default `22`) |
| `CR_PAT` | GitHub Personal Access Token (dengan permission `read:packages`) untuk docker pull di server |

### 7.2 File `.env.production` di Server
File `.env.production` disimpan langsung di server pada `/opt/wms/.env.production` dan dilindungi dengan izin akses ketat:
```bash
chmod 600 /opt/wms/.env.production
```

Contoh isi `/opt/wms/.env.production`:
```env
# Database Credentials
POSTGRES_USER=wms_owner
POSTGRES_PASSWORD=GENERATE_PASSWORD_YANG_SANGAT_KUAT_DI_SINI
POSTGRES_DB=wms_production

# Application Database Connection Strings
DATABASE_URL=postgresql://wms_app:APP_PASSWORD@postgres:5432/wms_production
MIGRATION_DATABASE_URL=postgresql://wms_owner:OWNER_PASSWORD@postgres:5432/wms_production

# JWT & Keamanan
JWT_SECRET=STRING_ACAK_MINIMAL_32_KARAKTER_UNTUK_PRODUKSI
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7

# Konfigurasi Cookie & CORS
COOKIE_SECURE=True
FRONTEND_ORIGINS=["https://wms.perusahaan.com"]

# Proteksi Login
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15
```

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
   ssh deployer@server-ip
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
