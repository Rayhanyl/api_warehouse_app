---
title: Documentation Change Management
description: Workflow perubahan, sinkronisasi, dan resolusi konflik dokumentasi
document_type: process
status: approved
version: 1.0
last_updated: 2026-11-03
source_of_truth: true
---

# Documentation Change Management

## Workflow

1. Identifikasi perubahan dan dokumen sumber yang terdampak.
2. Periksa PRD, struktur kode, migrasi, implementasi, dan test yang relevan.
3. Ubah sumber kebenaran terlebih dahulu bila requirement memang disetujui.
4. Evaluasi dokumen turunan berdasarkan matriks dampak.
5. Sinkronkan indeks dan tautan relatif.
6. Jalankan validasi tautan serta test dokumentasi bila tersedia.
7. Catat discrepancy, asumsi, atau hal belum terverifikasi.

## Matriks dampak

| Perubahan | Evaluasi minimum |
| --- | --- |
| Requirement atau aturan bisnis | CORE, RULE_SYSTEM, API, QA |
| Skema atau migrasi | CORE, API, QA, repository terkait |
| Kontrak endpoint | CORE API Contract, API, QA |
| Arsitektur atau struktur folder | CORE, STANDARDS, QA |
| Engineering standard | Kode, review, QA, dokumentasi terkait |

## Resolusi konflik

Jangan memilih versi secara diam-diam. Catat file, heading, bukti, dampak, dan
status keputusan di [Documentation Audit](../CORE/DOCUMENTATION_AUDIT.md).
Jika konflik memerlukan keputusan bisnis atau arsitektur, hentikan perubahan
turunan dan minta konfirmasi pemilik proyek.

## Kriteria selesai

- Sumber kebenaran dan statusnya jelas.
- Tidak ada tautan ke lokasi lama.
- Dokumen turunan tidak menggandakan requirement.
- Temuan terbuka dan asumsi tetap terlihat.
- Implementasi dan test tidak diubah hanya untuk membuat dokumentasi tampak
  konsisten.
