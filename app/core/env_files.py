"""Resolusi berkas environment aktif (satu sumber untuk `Settings` dan runner migrasi).

Aturan pemilihan berkas:

* Default: `.env` lalu `.env.local` (berkas belakangan menimpa berkas sebelumnya;
  berkas yang tidak ada dilewati).
* Jika variabel OS `ENV_FILE` diisi, hanya berkas itu yang dipakai. Path relatif
  dihitung dari root proyek, dan berkas wajib ada agar salah ketik tidak diam-diam
  jatuh ke konfigurasi lain.

Variabel OS yang sudah diset selalu menang atas isi berkas apa pun.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE_VARIABLE = "ENV_FILE"
DEFAULT_ENV_FILES: tuple[str, ...] = (".env", ".env.local")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_env_files() -> tuple[Path, ...]:
    """Mengembalikan daftar berkas env berurutan dari prioritas terendah ke tertinggi."""
    explicit = os.environ.get(ENV_FILE_VARIABLE, "").strip()
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.is_file():
            raise RuntimeError(
                f"{ENV_FILE_VARIABLE} menunjuk ke berkas yang tidak ditemukan: {path}"
            )
        return (path,)
    return tuple(PROJECT_ROOT / name for name in DEFAULT_ENV_FILES)
