"""Pengiriman notifikasi error aplikasi real-time ke Telegram Bot API (Tahap 13 / Poin 6).

Fitur utama:
- Menangkap informasi konteks error terstruktur (service, environment, jenis error,
  pesan error, waktu kejadian WIB+UTC, file & baris kode, Trace ID / X-Request-ID).
- Menyaring informasi sensitif (password, token, URL berkredensial, JWT, PII email/telepon)
  sebelum pesan dikirim ke Telegram maupun saat mencatat kegagalan kirim ke log lokal.
- Non-blocking terhadap respons HTTP klien (dijalankan melalui Starlette BackgroundTask).
- Deduplikasi / cooldown per signature error agar tidak membanjiri chat atau terkena
  rate-limit HTTP 429 Telegram saat terjadi lonjakan error identik.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
from pathlib import Path
import sys
import threading
import time
import traceback
from typing import Any

from fastapi import Request
import httpx
from starlette.background import BackgroundTask

from app.core.config import settings
from app.core.logging import logger, request_id_ctx
from app.core.sanitizer import sanitize_text, sanitize_url_path_and_query

_WIB_TZ = timezone(timedelta(hours=7))
_PROJECT_ROOT_STR = str(Path(__file__).resolve().parents[2]).replace("\\", "/").rstrip("/")
_APP_PATH_PREFIXES = ("app/", "db/", "scripts/", "tests/")
_PLACEHOLDER_MARKERS = ("<", "ganti-", "placeholder", "your_")
_MAX_TELEGRAM_TEXT_LENGTH = 3900
_MAX_COOLDOWN_ENTRIES = 1000

_cooldown_lock = threading.Lock()
_last_sent_monotonic: dict[tuple[str, str, str], float] = {}
_suppressed_counts: dict[tuple[str, str, str], int] = {}


@dataclass(frozen=True, slots=True)
class ErrorAlertContext:
    """Snapshot konteks error yang aman dikirim ke Telegram tanpa menyimpan objek Request/secret."""

    service_name: str
    environment: str
    error_type: str
    error_message: str
    occurred_at: datetime
    trace_id: str
    endpoint: str | None
    http_status: int | None
    app_location: str | None
    root_location: str | None
    traceback_excerpt: str | None
    cooldown_key: tuple[str, str, str]
    is_test: bool = False


def reset_rate_limit_cache() -> None:
    """Mengosongkan cache cooldown deduplikasi (digunakan oleh unit test)."""
    with _cooldown_lock:
        _last_sent_monotonic.clear()
        _suppressed_counts.clear()


def is_telegram_configured() -> bool:
    """Memeriksa apakah fitur Telegram aktif dan kredensial dasarnya valid (bukan placeholder)."""
    if not settings.telegram_enabled:
        return False
    token = (settings.telegram_bot_token or "").strip()
    chat_id = (settings.telegram_chat_id or "").strip()
    if not token or not chat_id:
        return False
    token_lower = token.lower()
    chat_lower = chat_id.lower()
    if any(marker in token_lower for marker in _PLACEHOLDER_MARKERS):
        return False
    if any(marker in chat_lower for marker in _PLACEHOLDER_MARKERS):
        return False
    return True


def _relativize_path(raw_path: str) -> str:
    normalized = raw_path.replace("\\", "/")
    if _PROJECT_ROOT_STR and normalized.startswith(_PROJECT_ROOT_STR + "/"):
        return normalized[len(_PROJECT_ROOT_STR) + 1 :]
    if "/site-packages/" in normalized:
        return "site-packages/" + normalized.split("/site-packages/", 1)[1]
    for marker in ("/app/", "/db/", "/scripts/"):
        idx = normalized.rfind(marker)
        if idx != -1:
            return normalized[idx + 1 :]
    return normalized


def _format_frame(frame: traceback.FrameSummary) -> str:
    rel = _relativize_path(frame.filename)
    return f"{rel}:{frame.lineno} ({frame.name})"


def extract_error_locations(
    exc: BaseException,
) -> tuple[str | None, str | None, str | None]:
    """Mengambil lokasi error aplikasi, titik terdalam, serta ringkasan stacktrace tersanitasi."""
    tb = exc.__traceback__
    target_exc: BaseException = exc
    while tb is None and target_exc.__cause__ is not None:
        target_exc = target_exc.__cause__
        tb = target_exc.__traceback__

    if tb is None:
        return None, None, None

    frames = traceback.extract_tb(tb)
    if not frames:
        return None, None, None

    app_frames = [
        frame
        for frame in frames
        if _relativize_path(frame.filename).startswith(_APP_PATH_PREFIXES)
    ]
    non_middleware_frames = [
        frame
        for frame in app_frames
        if not _relativize_path(frame.filename).endswith("app/core/middleware.py")
    ]
    chosen_app_frames = non_middleware_frames or app_frames
    app_location = _format_frame(chosen_app_frames[-1]) if chosen_app_frames else None
    deepest_location = _format_frame(frames[-1])
    root_location = (
        deepest_location if deepest_location != app_location else None
    )

    excerpt_lines: list[str] = []
    for frame in frames[-5:]:
        rel = _relativize_path(frame.filename)
        excerpt_lines.append(f'File "{rel}", line {frame.lineno}, in {frame.name}')
        if frame.line:
            clean_line = sanitize_text(frame.line.strip(), max_length=180)
            excerpt_lines.append(f"  {clean_line}")

    traceback_excerpt = "\n".join(excerpt_lines)
    if len(traceback_excerpt) > 1200:
        traceback_excerpt = "...\n" + traceback_excerpt[-1180:]
    return app_location, root_location, traceback_excerpt


def build_error_alert_context(
    exc: BaseException,
    *,
    request: Request | None = None,
    trace_id: str | None = None,
    http_status: int | None = 500,
    source: str | None = None,
    is_test: bool = False,
) -> ErrorAlertContext:
    """Membentuk ErrorAlertContext tersanitasi dari exception & metadata request."""
    state_trace_id = (
        getattr(request.state, "request_id", None) if request is not None else None
    )
    resolved_trace_id = (
        trace_id or state_trace_id or request_id_ctx.get("-") or "-"
    ).strip() or "-"

    if request is not None:
        clean_path = sanitize_url_path_and_query(request.url.path, request.url.query)
        endpoint: str | None = f"{request.method} {clean_path}"
        cooldown_endpoint = f"{request.method} {sanitize_text(request.url.path or '/')}"
    else:
        endpoint = sanitize_text(source, max_length=200) if source else None
        cooldown_endpoint = endpoint or "-"

    error_type = type(exc).__qualname__
    raw_msg = str(exc).strip()
    error_message = sanitize_text(raw_msg, max_length=600) if raw_msg else error_type

    app_location, root_location, traceback_excerpt = extract_error_locations(exc)
    loc_key = app_location or root_location or "-"

    return ErrorAlertContext(
        service_name=settings.app_name,
        environment=settings.app_env,
        error_type=error_type,
        error_message=error_message,
        occurred_at=datetime.now(timezone.utc),
        trace_id=resolved_trace_id,
        endpoint=endpoint,
        http_status=http_status,
        app_location=app_location,
        root_location=root_location,
        traceback_excerpt=traceback_excerpt,
        cooldown_key=(error_type, loc_key, cooldown_endpoint),
        is_test=is_test,
    )


def _acquire_send_slot(key: tuple[str, str, str]) -> tuple[bool, int]:
    """Mengatur cooldown deduplikasi agar Telegram tidak dibanjiri error yang sama berturut-turut."""
    cooldown = settings.telegram_cooldown_seconds
    now = time.monotonic()
    with _cooldown_lock:
        if cooldown <= 0:
            suppressed = _suppressed_counts.pop(key, 0)
            _last_sent_monotonic[key] = now
            return True, suppressed

        last_sent = _last_sent_monotonic.get(key)
        if last_sent is not None and (now - last_sent) < cooldown:
            _suppressed_counts[key] = _suppressed_counts.get(key, 0) + 1
            return False, 0

        if len(_last_sent_monotonic) >= _MAX_COOLDOWN_ENTRIES:
            _last_sent_monotonic.clear()
            _suppressed_counts.clear()

        suppressed = _suppressed_counts.pop(key, 0)
        _last_sent_monotonic[key] = now
        return True, suppressed


def format_telegram_error_html(
    ctx: ErrorAlertContext, *, suppressed_count: int = 0
) -> str:
    """Memformat ErrorAlertContext menjadi pesan HTML Telegram yang aman & <= 3900 karakter."""
    env_label = html.escape(ctx.environment.upper(), quote=False)
    service_label = html.escape(ctx.service_name, quote=False)
    prefix = "🧪 <b>[TEST SIMULASI]</b> " if ctx.is_test else "🚨 "

    wib_str = ctx.occurred_at.astimezone(_WIB_TZ).strftime("%Y-%m-%d %H:%M:%S WIB")
    utc_str = ctx.occurred_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        f"{prefix}<b>[{env_label}] ERROR APLIKASI — {service_label}</b>",
        "",
        f"<b>Jenis Error:</b> <code>{html.escape(ctx.error_type, quote=False)}</code>",
        f"<b>Waktu:</b> <code>{wib_str}</code> (<code>{utc_str}</code>)",
        f"<b>Trace ID:</b> <code>{html.escape(ctx.trace_id, quote=False)}</code>",
    ]

    if ctx.endpoint:
        status_part = (
            f" (HTTP <code>{ctx.http_status}</code>)" if ctx.http_status is not None else ""
        )
        lines.append(
            f"<b>Endpoint:</b> <code>{html.escape(ctx.endpoint, quote=False)}</code>{status_part}"
        )

    if ctx.app_location:
        lines.append(
            f"<b>Lokasi Aplikasi:</b> <code>{html.escape(ctx.app_location, quote=False)}</code>"
        )
    if ctx.root_location:
        lines.append(
            f"<b>Lokasi Terdalam:</b> <code>{html.escape(ctx.root_location, quote=False)}</code>"
        )
    if not ctx.app_location and not ctx.root_location:
        lines.append("<b>Lokasi:</b> <i>Tidak tersedia</i>")

    if suppressed_count > 0:
        lines.append(
            f"<b>Catatan Flood Guard:</b> +{suppressed_count} error serupa terjadi selama jeda cooldown"
        )

    lines.extend(
        [
            "",
            "<b>Pesan Error:</b>",
            f"<pre>{html.escape(ctx.error_message, quote=False)}</pre>",
        ]
    )

    body_without_trace = "\n".join(lines)
    if ctx.traceback_excerpt:
        remaining = _MAX_TELEGRAM_TEXT_LENGTH - len(body_without_trace) - 60
        if remaining > 120:
            excerpt = ctx.traceback_excerpt
            if len(excerpt) > remaining:
                excerpt = "...\n" + excerpt[-(remaining - 4) :]
            trace_block = (
                "\n<b>Ringkasan Stacktrace:</b>\n"
                f"<pre>{html.escape(excerpt, quote=False)}</pre>"
            )
            full_text = body_without_trace + trace_block
            if len(full_text) <= _MAX_TELEGRAM_TEXT_LENGTH:
                return full_text

    if len(body_without_trace) > _MAX_TELEGRAM_TEXT_LENGTH:
        # Jaga tag <pre> tetap tertutup jika pesan error terlalu panjang
        overflow = len(body_without_trace) - _MAX_TELEGRAM_TEXT_LENGTH
        trimmed_msg = ctx.error_message[: max(40, len(ctx.error_message) - overflow - 20)] + "... [truncated]"
        lines[-1] = f"<pre>{html.escape(trimmed_msg, quote=False)}</pre>"
        return "\n".join(lines)[:_MAX_TELEGRAM_TEXT_LENGTH]

    return body_without_trace


def _build_telegram_payload(text: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chat_id": (settings.telegram_chat_id or "").strip(),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if settings.telegram_thread_id is not None:
        payload["message_thread_id"] = settings.telegram_thread_id
    return payload


def _handle_telegram_response(response: httpx.Response) -> bool:
    if response.status_code == 200:
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("ok") is True:
                return True
        except ValueError:
            pass
    safe_body = sanitize_text(response.text, max_length=300)
    logger.warning(
        "Telegram sendMessage gagal (HTTP %s): %s",
        response.status_code,
        safe_body,
    )
    return False


async def send_telegram_message_async(
    text: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    """Mengirim satu pesan teks HTML ke Bot Telegram secara asynchronous tanpa melempar exception."""
    if not is_telegram_configured():
        return False

    token = (settings.telegram_bot_token or "").strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = _build_telegram_payload(text)

    try:
        async with httpx.AsyncClient(
            timeout=settings.telegram_timeout_seconds,
            transport=transport,
        ) as client:
            response = await client.post(url, json=payload)
        return _handle_telegram_response(response)
    except Exception as exc:
        logger.warning(
            "Gagal menghubungi API Telegram: %s",
            sanitize_text(str(exc), max_length=250),
        )
        return False


def send_telegram_message_sync(
    text: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> bool:
    """Mengirim satu pesan teks HTML ke Bot Telegram secara sinkron (untuk CLI --test / fallback)."""
    if not is_telegram_configured():
        return False

    token = (settings.telegram_bot_token or "").strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = _build_telegram_payload(text)

    try:
        with httpx.Client(
            timeout=settings.telegram_timeout_seconds,
            transport=transport,
        ) as client:
            response = client.post(url, json=payload)
        return _handle_telegram_response(response)
    except Exception as exc:
        logger.warning(
            "Gagal menghubungi API Telegram: %s",
            sanitize_text(str(exc), max_length=250),
        )
        return False


async def dispatch_error_alert_async(
    ctx: ErrorAlertContext,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    """Mengirim ErrorAlertContext ke Telegram dengan cooldown deduplikasi."""
    if not is_telegram_configured():
        if settings.telegram_enabled:
            logger.warning(
                "TELEGRAM_ENABLED=True tetapi TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum lengkap atau masih placeholder."
            )
        return False

    allowed, suppressed = _acquire_send_slot(ctx.cooldown_key)
    if not allowed:
        logger.info(
            "Notifikasi Telegram untuk %s dilewati sementara (dalam cooldown).",
            ctx.error_type,
        )
        return False

    message_html = format_telegram_error_html(ctx, suppressed_count=suppressed)
    return await send_telegram_message_async(message_html, transport=transport)


def create_error_background_task(
    exc: BaseException,
    *,
    request: Request | None = None,
    trace_id: str | None = None,
    http_status: int | None = 500,
    source: str | None = None,
) -> BackgroundTask | None:
    """Membentuk BackgroundTask non-blocking jika Telegram aktif, atau None jika nonaktif."""
    if not is_telegram_configured():
        return None
    ctx = build_error_alert_context(
        exc,
        request=request,
        trace_id=trace_id,
        http_status=http_status,
        source=source,
    )
    return BackgroundTask(dispatch_error_alert_async, ctx)


async def notify_exception_async(
    exc: BaseException,
    *,
    request: Request | None = None,
    trace_id: str | None = None,
    http_status: int | None = 500,
    source: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    """Helper langsung untuk membangun konteks error dan mengirim notifikasi Telegram."""
    if not is_telegram_configured():
        return False
    ctx = build_error_alert_context(
        exc,
        request=request,
        trace_id=trace_id,
        http_status=http_status,
        source=source,
    )
    return await dispatch_error_alert_async(ctx, transport=transport)


def _run_cli_test() -> int:
    if not is_telegram_configured():
        print(
            "Telegram belum aktif/lengkap. Pastikan TELEGRAM_ENABLED=True, "
            "TELEGRAM_BOT_TOKEN, dan TELEGRAM_CHAT_ID sudah diisi di .env."
        )
        return 1

    try:
        raise RuntimeError(
            "Simulasi uji notifikasi error real-time (kredensial contoh postgres://wms:Secret123@db:5432/wms "
            "dan email operator@contoh.id harus tersamarkan)."
        )
    except RuntimeError as sim_exc:
        ctx = build_error_alert_context(
            sim_exc,
            trace_id="test-trace-telegram-cli-001",
            http_status=500,
            source="CLI --test /api/v1/health",
            is_test=True,
        )
        msg = format_telegram_error_html(ctx)
        ok = send_telegram_message_sync(msg)
        if ok:
            print("Berhasil mengirim notifikasi uji Telegram ke chat tujuan.")
            return 0
        print("Gagal mengirim notifikasi uji Telegram. Periksa log peringatan di atas.")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Uji konektivitas notifikasi error aplikasi WMS ke Bot Telegram."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Kirim satu pesan simulasi error tersanitasi ke Telegram Bot API.",
    )
    args = parser.parse_args(argv)
    if args.test:
        return _run_cli_test()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
