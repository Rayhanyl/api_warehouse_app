---
title: Documentation Standards
description: Standar penulisan dan pemeliharaan dokumentasi WMS
document_type: standard
status: approved
version: 1.0
last_updated: 2026-11-03
source_of_truth: true
---

# Documentation Standards

## Prinsip

- Satu informasi memiliki satu pemilik sumber kebenaran.
- Dokumen turunan menggunakan tautan relatif, bukan salinan spesifikasi.
- Perilaku aktual, requirement, asumsi, dan hasil test diberi label berbeda.
- Bahasa utama adalah Bahasa Indonesia yang jelas dan konsisten.
- Jangan menulis secret, token, password, atau data sensitif.

## Metadata

Dokumen spesifikasi dan standar baru menggunakan front matter yang relevan:

```yaml
---
title: Document Title
description: Short description
document_type: specification
status: approved
version: 1.0
last_updated: YYYY-MM-DD
source_of_truth: false
---
```

Metadata tidak boleh digunakan untuk mempromosikan draft atau catatan audit
menjadi requirement.

## Format dan tautan

- Gunakan heading berurutan, tabel untuk data terstruktur, dan fenced code
  block dengan bahasa yang sesuai.
- Nama file baru menggunakan huruf kecil dan tanda hubung bila diperlukan.
- Tautan internal harus relatif dan diuji setelah pemindahan file.
- README berfungsi sebagai indeks; detail tetap berada di dokumen pemilik.

## Status informasi

Gunakan label `Approved`, `Draft`, `Perlu Ditinjau`, `Aktual`, atau
`Belum Terverifikasi` sesuai bukti. Klaim benchmark dan hasil test harus
menyebut tanggal, lingkungan, dan command bila tersedia.
