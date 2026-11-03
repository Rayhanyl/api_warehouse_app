# API Contract — Ringkasan CORE

Dokumen ini menetapkan batas kontrak API tingkat sistem tanpa menyalin detail
setiap endpoint. Detail operasional dan contoh request/response berada di
[API/README.md](../API/README.md) dan dokumen modul di folder tersebut.

## Kontrak global

- Base path modul: `/api/v1`.
- Format payload: JSON.
- Autentikasi: JWT HS256 melalui header `Authorization: Bearer <access-token>`.
- Waktu: ISO 8601 dengan timezone.
- Kuantitas: string desimal; penyimpanan PostgreSQL menggunakan `NUMERIC(18,4)`.
- Pagination: `limit` dan `offset` sesuai utilitas pagination aktual.
- Error: objek `error` dengan `code`, `message`, dan `details` bila tersedia.
- Request ID: header `X-Request-ID` dipertahankan atau dibuat server.

## Ownership

CORE hanya menetapkan prinsip dan katalog kontrak. Route dan schema aktual
menentukan bentuk endpoint; repository tidak boleh menjadi sumber kontrak HTTP.
Jika implementasi berbeda dari PRD, catat di
[Documentation Audit](DOCUMENTATION_AUDIT.md) dan dokumentasikan perilaku aktual
di [API/README.md](../API/README.md).

## Rujukan

- Kebutuhan dan acceptance criteria:
  [PRODUCT_REQUIREMENTS_DOCUMENT.MD](PRODUCT_REQUIREMENTS_DOCUMENT.MD).
- Struktur layer:
  [FOLDER_STRUCTURE.MD](FOLDER_STRUCTURE.MD).
- Detail endpoint:
  [API/README.md](../API/README.md).
