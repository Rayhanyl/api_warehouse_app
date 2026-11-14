#!/usr/bin/env python3
"""Daemon pemantau status container Docker real-time dengan notifikasi Telegram (Tahap 13 / Poin 7).

Dirancang tanpa dependensi pihak ketiga (hanya Python 3 stdlib) agar dapat langsung dijalankan:
1) Sebagai service systemd di server host (menggunakan user `deployer` di grup `docker`).
2) Sebagai container sidecar ringan dengan mount `/var/run/docker.sock:ro` (fallback HTTP over AF_UNIX).
3) Secara lokal saat pengembangan di Windows / Linux / macOS menggunakan Docker CLI.

Kondisi container yang dipantau:
- Up           : Container berhasil berjalan (`start`, `health_status: healthy`)
- Down         : Container service berhenti (`die` exit 0 pada service non-oneoff, atau hilang/stopped saat poll)
- Exited       : Container tugas sekali jalan selesai (`die` exit 0 pada oneoff/migration/restart=no)
- Crash/Restart: Container gagal (`die` exit != 0, `OOMKilled`, `oom`, `restart`, `health_status: unhealthy`,
                 maupun pola crash-restart berulang dalam jendela waktu tertentu)
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
import http.client
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Iterator, Protocol
import urllib.error
import urllib.parse
import urllib.request

_WIB_TZ = timezone(timedelta(hours=7))
_MAX_TELEGRAM_TEXT_LENGTH = 3900
_PLACEHOLDER_MARKERS = ("<", "ganti-", "placeholder", "your_")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | docker-monitor | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("wms.docker_monitor")

# ---------------------------------------------------------------------------
# Sanitasi mandiri (menghindari ketergantungan import `app` di VPS host)
# ---------------------------------------------------------------------------
_URL_CREDENTIAL_RE = re.compile(
    r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:/\s@]+:)([^\s/]+)(@[A-Za-z0-9._-]+)"
)
_TELEGRAM_BOT_TOKEN_RE = re.compile(r"(\bbot)?\d{6,15}:[A-Za-z0-9_-]{25,}\b")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_AUTH_SCHEME_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{6,}")
_PG_KEY_DETAIL_RE = re.compile(
    r"(?i)(Key\s*\([^)]*(?:email|phone|no_hp|nik|npwp|ktp|password|token|secret)[^)]*\)\s*=\s*\()([^)]+)(\))"
)
_KV_SENSITIVE_RE = re.compile(
    r"(?i)(\b[a-z0-9_.-]*(?:password|passwd|pwd|secret|token|authorization|cookie|"
    r"api_?key|private_key|credential|email|e-mail|phone|no_hp|telepon|alamat|"
    r"address|nik|npwp|ktp)[a-z0-9_.-]*[\"']?\s*[:=]\s*)"
    r"(?:\[REDACTED(?:_[A-Z0-9_]+)?\]|\"[^\"]*\"|'[^']*'|[^\s,;&}\]\)]+)"
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_ID_PHONE_RE = re.compile(r"(?<!\w)(?:\+62|08)\d[\d-]{6,13}\d(?!\w)")


def sanitize_text(text: str, *, max_length: int | None = None) -> str:
    """Menyamarkan kredensial, token bot, URL DB berkredensial, JWT, dan PII sebelum dikirim/dicatat."""
    if not text:
        return ""
    cleaned = _URL_CREDENTIAL_RE.sub(r"\1[REDACTED]\3", text)
    cleaned = _TELEGRAM_BOT_TOKEN_RE.sub(
        lambda m: f"{m.group(1) or ''}[REDACTED_BOT_TOKEN]",
        cleaned,
    )
    cleaned = _JWT_RE.sub("[REDACTED_JWT]", cleaned)
    cleaned = _AUTH_SCHEME_RE.sub(r"\1 [REDACTED]", cleaned)
    cleaned = _PG_KEY_DETAIL_RE.sub(r"\1[REDACTED]\3", cleaned)
    cleaned = _KV_SENSITIVE_RE.sub(r"\1[REDACTED]", cleaned)
    cleaned = _EMAIL_RE.sub("[REDACTED_EMAIL]", cleaned)
    cleaned = _ID_PHONE_RE.sub("[REDACTED_PHONE]", cleaned)

    if max_length is not None and len(cleaned) > max_length:
        suffix = "... [truncated]"
        cut = max(0, max_length - len(suffix))
        cleaned = f"{cleaned[:cut]}{suffix}"
    return cleaned


# ---------------------------------------------------------------------------
# Pemuatan .env & konfigurasi
# ---------------------------------------------------------------------------
def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    content = path.read_text(encoding="utf-8-sig")
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def load_env_defaults(explicit_env_file: str | None = None) -> None:
    """Mengisi os.environ dari berkas env tanpa menimpa variabel OS yang sudah ada."""
    candidates: list[Path] = []
    if explicit_env_file:
        path = Path(explicit_env_file)
        if not path.is_file():
            raise FileNotFoundError(f"Berkas env tidak ditemukan: {path}")
        candidates.append(path)
    else:
        cwd = Path.cwd()
        script_root = Path(__file__).resolve().parents[1]
        for base in (script_root, cwd):
            for name in (".env", ".env.local", ".env.docker", ".env.production"):
                p = base / name
                if p.is_file() and p not in candidates:
                    candidates.append(p)

    merged: dict[str, str] = {}
    for candidate in candidates:
        merged.update(_parse_env_file(candidate))

    for key, val in merged.items():
        if key not in os.environ:
            os.environ[key] = val


@dataclass(frozen=True, slots=True)
class MonitorConfig:
    """Konfigurasi pemantau container Docker & pengiriman ke Telegram."""

    enabled: bool
    bot_token: str
    chat_id: str
    thread_id: int | None
    app_name: str
    environment: str
    host_label: str
    filters: tuple[str, ...]
    cooldown_seconds: int
    crash_window_seconds: int
    crash_threshold: int
    poll_interval_seconds: int
    log_lines: int
    socket_path: str
    timeout_seconds: float

    @classmethod
    def from_env(cls) -> "MonitorConfig":
        raw_enabled = os.environ.get(
            "DOCKER_MONITOR_ENABLED",
            os.environ.get("TELEGRAM_ENABLED", "false"),
        ).strip().lower()
        enabled = raw_enabled in {"1", "true", "yes", "on"}

        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        raw_thread = os.environ.get("TELEGRAM_THREAD_ID", "").strip()
        thread_id = int(raw_thread) if raw_thread else None

        raw_filters = os.environ.get("DOCKER_MONITOR_FILTERS", "wms").strip()
        if raw_filters.lower() in {"*", "all", ""}:
            filters: tuple[str, ...] = ()
        else:
            filters = tuple(
                part.strip().lower()
                for part in raw_filters.split(",")
                if part.strip()
            )

        return cls(
            enabled=enabled,
            bot_token=token,
            chat_id=chat_id,
            thread_id=thread_id,
            app_name=os.environ.get("APP_NAME", "JejakStok WMS").strip() or "JejakStok WMS",
            environment=os.environ.get("APP_ENV", "local").strip() or "local",
            host_label=os.environ.get("DOCKER_MONITOR_HOST_LABEL", "").strip()
            or socket.gethostname(),
            filters=filters,
            cooldown_seconds=max(
                0, int(os.environ.get("DOCKER_MONITOR_COOLDOWN_SECONDS", "30"))
            ),
            crash_window_seconds=max(
                30, int(os.environ.get("DOCKER_MONITOR_CRASH_WINDOW_SECONDS", "300"))
            ),
            crash_threshold=max(
                2, int(os.environ.get("DOCKER_MONITOR_CRASH_THRESHOLD", "2"))
            ),
            poll_interval_seconds=max(
                5, int(os.environ.get("DOCKER_MONITOR_POLL_INTERVAL_SECONDS", "30"))
            ),
            log_lines=max(0, int(os.environ.get("DOCKER_MONITOR_LOG_LINES", "12"))),
            socket_path=os.environ.get(
                "DOCKER_SOCKET_PATH", "/var/run/docker.sock"
            ).strip()
            or "/var/run/docker.sock",
            timeout_seconds=max(
                1.0, float(os.environ.get("TELEGRAM_TIMEOUT_SECONDS", "5.0"))
            ),
        )

    def has_valid_telegram_credentials(self) -> bool:
        if not self.bot_token or not self.chat_id:
            return False
        t_low = self.bot_token.lower()
        c_low = self.chat_id.lower()
        return not any(m in t_low or m in c_low for m in _PLACEHOLDER_MARKERS)


# ---------------------------------------------------------------------------
# Backend Docker (CLI + Unix Socket AF_UNIX tanpa dependensi eksternal)
# ---------------------------------------------------------------------------
class DockerBackend(Protocol):
    def stream_events(self) -> Iterator[dict[str, Any]]: ...
    def inspect_container(self, container_id: str) -> dict[str, Any] | None: ...
    def list_containers(self) -> list[dict[str, Any]]: ...
    def tail_logs(self, container_id: str, tail: int) -> str: ...


class CliDockerBackend:
    """Backend pemantau Docker memakai perintah CLI `docker`."""

    def stream_events(self) -> Iterator[dict[str, Any]]:
        cmd = [
            "docker",
            "events",
            "--filter",
            "type=container",
            "--filter",
            "event=start",
            "--filter",
            "event=die",
            "--filter",
            "event=restart",
            "--filter",
            "event=oom",
            "--filter",
            "event=health_status",
            "--format",
            "{{json .}}",
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
            rc = proc.wait()
            if rc != 0:
                err = proc.stderr.read().strip() if proc.stderr else ""
                raise RuntimeError(f"docker events berhenti dengan kode {rc}: {err}")
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def inspect_container(self, container_id: str) -> dict[str, Any] | None:
        res = subprocess.run(
            ["docker", "inspect", container_id],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return None
        try:
            data = json.loads(res.stdout)
            if isinstance(data, list) and data:
                return data[0]
        except json.JSONDecodeError:
            return None
        return None

    def list_containers(self) -> list[dict[str, Any]]:
        res = subprocess.run(
            ["docker", "ps", "-a", "-q"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        if res.returncode != 0:
            return []
        ids = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if not ids:
            return []
        insp = subprocess.run(
            ["docker", "inspect", *ids],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
        if insp.returncode != 0 or not insp.stdout.strip():
            return []
        try:
            data = json.loads(insp.stdout)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def tail_logs(self, container_id: str, tail: int) -> str:
        if tail <= 0:
            return ""
        res = subprocess.run(
            ["docker", "logs", "--tail", str(tail), container_id],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        combined = "\n".join(part for part in (res.stdout, res.stderr) if part).strip()
        return combined


class _UnixSocketHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float = 10.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self._socket_path = socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # type: ignore[attr-defined]
        sock.settimeout(self.timeout)
        sock.connect(self._socket_path)
        self.sock = sock


def _decode_docker_log_stream(raw: bytes) -> str:
    """Mendekode frame log multiplexed Docker (header 8-byte) atau teks TTY biasa."""
    if not raw:
        return ""
    pos = 0
    chunks: list[bytes] = []
    # Header frame multiplexed Docker: [stream_type(1), 0, 0, 0, size(4 big-endian)]
    while pos + 8 <= len(raw) and raw[pos] in (0, 1, 2) and raw[pos + 1 : pos + 4] == b"\x00\x00\x00":
        size = int.from_bytes(raw[pos + 4 : pos + 8], "big")
        pos += 8
        chunks.append(raw[pos : pos + size])
        pos += size
    if chunks:
        return b"".join(chunks).decode("utf-8", errors="replace").strip()
    return raw.decode("utf-8", errors="replace").strip()


class UnixSocketDockerBackend:
    """Backend pemantau Docker langsung via `/var/run/docker.sock` (cocok di dalam container)."""

    def __init__(self, socket_path: str = "/var/run/docker.sock") -> None:
        self.socket_path = socket_path

    def _request(self, method: str, path: str, timeout: float = 10.0) -> tuple[int, bytes]:
        conn = _UnixSocketHTTPConnection(self.socket_path, timeout=timeout)
        try:
            conn.request(method, path)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def stream_events(self) -> Iterator[dict[str, Any]]:
        filters_json = json.dumps(
            {
                "type": ["container"],
                "event": ["start", "die", "restart", "oom", "health_status"],
            }
        )
        query = urllib.parse.urlencode({"filters": filters_json})
        conn = _UnixSocketHTTPConnection(self.socket_path, timeout=None)  # type: ignore[arg-type]
        try:
            conn.request("GET", f"/events?{query}")
            resp = conn.getresponse()
            if resp.status != 200:
                raise RuntimeError(f"Docker socket /events HTTP {resp.status}")
            while True:
                raw_line = resp.fp.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        finally:
            conn.close()

    def inspect_container(self, container_id: str) -> dict[str, Any] | None:
        try:
            status, body = self._request(
                "GET", f"/containers/{urllib.parse.quote(container_id)}/json"
            )
            if status != 200:
                return None
            data = json.loads(body.decode("utf-8", errors="replace"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def list_containers(self) -> list[dict[str, Any]]:
        try:
            status, body = self._request("GET", "/containers/json?all=true")
            if status != 200:
                return []
            summaries = json.loads(body.decode("utf-8", errors="replace"))
            result: list[dict[str, Any]] = []
            for item in summaries:
                cid = item.get("Id")
                if cid:
                    inspected = self.inspect_container(cid)
                    if inspected:
                        result.append(inspected)
            return result
        except Exception:
            return []

    def tail_logs(self, container_id: str, tail: int) -> str:
        if tail <= 0:
            return ""
        try:
            status, body = self._request(
                "GET",
                f"/containers/{urllib.parse.quote(container_id)}/logs?stdout=1&stderr=1&tail={tail}",
            )
            if status != 200:
                return ""
            return _decode_docker_log_stream(body)
        except Exception:
            return ""


def select_docker_backend(mode: str, socket_path: str) -> DockerBackend:
    """Memilih backend Docker CLI atau Unix Socket sesuai lingkungan eksekusi."""
    if mode == "cli":
        if not shutil.which("docker"):
            raise RuntimeError("Perintah `docker` CLI tidak ditemukan di PATH.")
        return CliDockerBackend()
    if mode == "socket":
        if not hasattr(socket, "AF_UNIX") or not os.path.exists(socket_path):
            raise RuntimeError(f"Docker Unix socket tidak tersedia di {socket_path}.")
        return UnixSocketDockerBackend(socket_path)
    if shutil.which("docker"):
        return CliDockerBackend()
    if hasattr(socket, "AF_UNIX") and os.path.exists(socket_path):
        return UnixSocketDockerBackend(socket_path)
    raise RuntimeError(
        "Tidak dapat menemukan `docker` CLI maupun socket `/var/run/docker.sock`."
    )


# ---------------------------------------------------------------------------
# Pengirim Telegram berbasis stdlib (urllib)
# ---------------------------------------------------------------------------
def send_telegram_html(config: MonitorConfig, html_text: str) -> bool:
    """Mengirim pesan HTML ke API Telegram dengan proteksi token di log error."""
    if not config.has_valid_telegram_credentials():
        logger.warning(
            "Kredensial Telegram tidak lengkap atau masih placeholder; pesan dilewati."
        )
        return False

    url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": config.chat_id,
        "text": html_text[:4090],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if config.thread_id is not None:
        payload["message_thread_id"] = config.thread_id

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=config.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw)
            return bool(isinstance(parsed, dict) and parsed.get("ok") is True)
    except urllib.error.HTTPError as http_err:
        err_body = http_err.read().decode("utf-8", errors="replace")
        logger.warning(
            "Telegram API HTTP %s: %s",
            http_err.code,
            sanitize_text(err_body, max_length=250),
        )
        return False
    except Exception as exc:
        logger.warning(
            "Gagal mengirim notifikasi Telegram: %s",
            sanitize_text(str(exc), max_length=250),
        )
        return False


# ---------------------------------------------------------------------------
# Engine klasifikasi status & deteksi crash-loop
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ContainerAlert:
    container_name: str
    service_name: str
    status_category: str  # UP | DOWN | EXITED | CRASH_RESTART | UNHEALTHY
    status_label: str
    occurred_at: datetime
    reason: str
    log_excerpt: str | None = None
    suppressed_count: int = 0


def _parse_event_timestamp(event: dict[str, Any]) -> datetime:
    time_nano = event.get("timeNano")
    if isinstance(time_nano, (int, float)) and time_nano > 0:
        return datetime.fromtimestamp(time_nano / 1_000_000_000, tz=timezone.utc)
    ts = event.get("time")
    if isinstance(ts, (int, float)) and ts > 0:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.now(timezone.utc)


def _clean_container_name(raw_name: str) -> str:
    return raw_name.strip().lstrip("/")


def _extract_service_label(
    config: MonitorConfig,
    attrs: dict[str, Any],
    inspect_data: dict[str, Any] | None,
    container_name: str,
) -> str:
    labels: dict[str, Any] = {}
    if inspect_data:
        labels.update(inspect_data.get("Config", {}).get("Labels") or {})
    labels.update(attrs)

    service = str(labels.get("com.docker.compose.service") or "").strip()
    project = str(labels.get("com.docker.compose.project") or "").strip()
    image = str(
        (inspect_data or {}).get("Config", {}).get("Image")
        or attrs.get("image")
        or ""
    ).strip()

    parts: list[str] = []
    if service:
        parts.append(service)
    else:
        parts.append(container_name)
    meta: list[str] = [config.app_name]
    if project:
        meta.append(f"project: {project}")
    if image:
        meta.append(image)
    return f"{parts[0]} ({', '.join(meta)})"


def _is_oneoff_or_no_restart(
    container_name: str,
    attrs: dict[str, Any],
    inspect_data: dict[str, Any] | None,
) -> bool:
    labels: dict[str, Any] = {}
    if inspect_data:
        labels.update(inspect_data.get("Config", {}).get("Labels") or {})
    labels.update(attrs)
    if str(labels.get("com.docker.compose.oneoff") or "").lower() == "true":
        return True
    restart_policy = (
        (inspect_data or {})
        .get("HostConfig", {})
        .get("RestartPolicy", {})
        .get("Name", "")
    )
    if str(restart_policy).lower() in {"no", ""}:
        return "migration" in container_name.lower() or bool(
            labels.get("com.docker.compose.oneoff")
        )
    return False


def format_container_alert_html(
    config: MonitorConfig,
    alert: ContainerAlert,
    *,
    is_test: bool = False,
) -> str:
    """Memformat event status container menjadi pesan Telegram HTML <= 3900 karakter."""
    badge_map = {
        "UP": "🟢",
        "DOWN": "🔴",
        "EXITED": "ℹ️",
        "CRASH_RESTART": "🔥",
        "UNHEALTHY": "⚠️",
    }
    badge = badge_map.get(alert.status_category, "📦")
    test_prefix = "🧪 <b>[TEST SIMULASI]</b> " if is_test else ""
    env_label = html.escape(config.environment.upper(), quote=False)
    host_label = html.escape(config.host_label, quote=False)

    wib_str = alert.occurred_at.astimezone(_WIB_TZ).strftime("%Y-%m-%d %H:%M:%S WIB")
    utc_str = alert.occurred_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    clean_reason = sanitize_text(alert.reason, max_length=500)
    lines = [
        f"{test_prefix}{badge} <b>[{env_label}] STATUS CONTAINER DOCKER</b>",
        "",
        f"<b>Container:</b> <code>{html.escape(alert.container_name, quote=False)}</code>",
        f"<b>Service / Aplikasi:</b> <code>{html.escape(alert.service_name, quote=False)}</code>",
        f"<b>Status:</b> <b>{html.escape(alert.status_label, quote=False)}</b>",
        f"<b>Waktu Perubahan:</b> <code>{wib_str}</code> (<code>{utc_str}</code>)",
        f"<b>Host / Server:</b> <code>{host_label}</code>",
        f"<b>Detail / Penyebab:</b> {html.escape(clean_reason, quote=False)}",
    ]

    if alert.suppressed_count > 0:
        lines.append(
            f"<b>Catatan Cooldown:</b> +{alert.suppressed_count} event identik dilewati selama masa jeda."
        )

    base_text = "\n".join(lines)
    if alert.log_excerpt:
        remaining = _MAX_TELEGRAM_TEXT_LENGTH - len(base_text) - 70
        if remaining > 100:
            excerpt = alert.log_excerpt
            if len(excerpt) > remaining:
                excerpt = "...\n" + excerpt[-(remaining - 4) :]
            return (
                f"{base_text}\n\n<b>Potongan Log Terakhir (Tersanitasi):</b>\n"
                f"<pre>{html.escape(excerpt, quote=False)}</pre>"
            )

    return base_text[:_MAX_TELEGRAM_TEXT_LENGTH]


class DockerMonitorEngine:
    """Pemroses event Docker + deteksi crash-loop, dedup cooldown, dan snapshot polling."""

    def __init__(
        self,
        config: MonitorConfig,
        backend: DockerBackend,
        sender: Callable[[MonitorConfig, str], bool] = send_telegram_html,
    ) -> None:
        self.config = config
        self.backend = backend
        self.sender = sender
        self._lock = threading.Lock()
        self._crash_timestamps: dict[str, deque[float]] = {}
        self._last_start_time: dict[str, float] = {}
        self._last_sent_by_key: dict[tuple[str, str], float] = {}
        self._suppressed_by_key: dict[tuple[str, str], int] = {}
        self._last_polled_status: dict[str, str] = {}

    def matches_filter(self, container_name: str) -> bool:
        if not self.config.filters:
            return True
        low = container_name.lower()
        return any(f in low or low.startswith(f) for f in self.config.filters)

    def _should_send(self, container_name: str, category: str) -> tuple[bool, int]:
        key = (container_name, category)
        now = time.monotonic()
        cutoff = now - self.config.crash_window_seconds
        with self._lock:
            crash_q = self._crash_timestamps.get(container_name)
            if crash_q:
                while crash_q and crash_q[0] < cutoff:
                    crash_q.popleft()
            recent_crashes = len(crash_q) if crash_q else 0

            last_polled = self._last_polled_status.get(container_name)
            state_changed = last_polled is not None and last_polled != category
            self._last_polled_status[container_name] = category

            is_flapping = recent_crashes >= self.config.crash_threshold
            just_escalated = (
                category == "CRASH_RESTART"
                and recent_crashes == self.config.crash_threshold
            )

            cooldown = self.config.cooldown_seconds
            if cooldown <= 0 or (state_changed and not is_flapping) or just_escalated:
                suppressed = self._suppressed_by_key.pop(key, 0)
                self._last_sent_by_key[key] = now
                return True, suppressed

            last = self._last_sent_by_key.get(key)
            if last is not None and (now - last) < cooldown:
                self._suppressed_by_key[key] = self._suppressed_by_key.get(key, 0) + 1
                return False, 0

            suppressed = self._suppressed_by_key.pop(key, 0)
            self._last_sent_by_key[key] = now
            return True, suppressed

    def _record_crash_and_count(self, container_name: str) -> int:
        now = time.monotonic()
        cutoff = now - self.config.crash_window_seconds
        with self._lock:
            q = self._crash_timestamps.setdefault(container_name, deque())
            q.append(now)
            while q and q[0] < cutoff:
                q.popleft()
            return len(q)

    def _recent_crash_count(self, container_name: str) -> int:
        now = time.monotonic()
        cutoff = now - self.config.crash_window_seconds
        with self._lock:
            q = self._crash_timestamps.get(container_name)
            if not q:
                return 0
            while q and q[0] < cutoff:
                q.popleft()
            return len(q)

    def process_event(self, event: dict[str, Any]) -> ContainerAlert | None:
        """Mengonversi satu event mentah Docker menjadi ContainerAlert lalu mengirim jika lolos filter/cooldown."""
        action = str(event.get("Action") or event.get("status") or "").strip()
        actor = event.get("Actor") or {}
        cid = str(actor.get("ID") or event.get("id") or "").strip()
        attrs = actor.get("Attributes") or {}
        raw_name = str(attrs.get("name") or cid[:12] or "unknown")
        container_name = _clean_container_name(raw_name)

        if not self.matches_filter(container_name):
            return None

        inspect_data = self.backend.inspect_container(cid or container_name)
        service_name = _extract_service_label(
            self.config, attrs, inspect_data, container_name
        )
        occurred_at = _parse_event_timestamp(event)
        state = (inspect_data or {}).get("State") or {}
        restart_count = int((inspect_data or {}).get("RestartCount") or 0)
        state_error = sanitize_text(str(state.get("Error") or "").strip(), max_length=250)

        alert: ContainerAlert | None = None

        if action == "start":
            with self._lock:
                self._last_start_time[container_name] = time.monotonic()
            recent_crashes = self._recent_crash_count(container_name)
            if recent_crashes > 0 or restart_count > 0:
                status_label = "Up (Berjalan Setelah Restart/Recovery)"
                reason = (
                    f"Container kembali aktif berjalan (RestartCount={restart_count}, "
                    f"riwayat crash baru-baru ini={recent_crashes})."
                )
            else:
                status_label = "Up — Container berhasil berjalan"
                reason = "Container mulai berjalan normal."
            alert = ContainerAlert(
                container_name=container_name,
                service_name=service_name,
                status_category="UP",
                status_label=status_label,
                occurred_at=occurred_at,
                reason=reason,
            )

        elif action == "restart":
            with self._lock:
                last_start = self._last_start_time.get(container_name)
            # Hindari duplikasi bila event `start` sudah dikirim <3 detik sebelumnya dalam siklus docker restart
            if last_start is not None and (time.monotonic() - last_start) < 3.0:
                return None
            alert = ContainerAlert(
                container_name=container_name,
                service_name=service_name,
                status_category="CRASH_RESTART",
                status_label="Crash / Restart — Container mengalami restart",
                occurred_at=occurred_at,
                reason=f"Event restart Docker diterima (RestartCount={restart_count}).",
            )

        elif action == "oom":
            self._record_crash_and_count(container_name)
            alert = ContainerAlert(
                container_name=container_name,
                service_name=service_name,
                status_category="CRASH_RESTART",
                status_label="Crash (OOMKilled) — Container kehabisan memori",
                occurred_at=occurred_at,
                reason="Kernel memicu Out-Of-Memory (OOM) pada container.",
            )

        elif action.startswith("health_status:"):
            health_state = action.split(":", 1)[1].strip().lower()
            if health_state == "healthy":
                alert = ContainerAlert(
                    container_name=container_name,
                    service_name=service_name,
                    status_category="UP",
                    status_label="Up (Healthy) — Healthcheck kembali sehat",
                    occurred_at=occurred_at,
                    reason="Pemeriksaan healthcheck container kembali berstatus healthy.",
                )
            elif health_state == "unhealthy":
                health_logs = (state.get("Health") or {}).get("Log") or []
                last_output = ""
                if health_logs:
                    last_output = sanitize_text(
                        str(health_logs[-1].get("Output") or "").strip(),
                        max_length=250,
                    )
                reason = "Pemeriksaan healthcheck container gagal (unhealthy)."
                if last_output:
                    reason += f" Output: {last_output}"
                alert = ContainerAlert(
                    container_name=container_name,
                    service_name=service_name,
                    status_category="UNHEALTHY",
                    status_label="Degraded / Unhealthy — Healthcheck gagal",
                    occurred_at=occurred_at,
                    reason=reason,
                )

        elif action == "die":
            exit_code_raw = attrs.get("exitCode")
            if exit_code_raw is None:
                exit_code_raw = state.get("ExitCode", 0)
            try:
                exit_code = int(exit_code_raw)
            except (TypeError, ValueError):
                exit_code = -1

            oom_killed = bool(state.get("OOMKilled", False))
            oneoff = _is_oneoff_or_no_restart(container_name, attrs, inspect_data)

            if oom_killed or exit_code != 0:
                crashes = self._record_crash_and_count(container_name)
                if oom_killed:
                    status_label = f"Crash (OOMKilled) — Kehabisan RAM (Exit Code {exit_code})"
                    reason = "Container dihentikan kernel karena kehabisan memori (OOMKilled=True)."
                elif crashes >= self.config.crash_threshold or restart_count >= self.config.crash_threshold:
                    window_min = max(1, self.config.crash_window_seconds // 60)
                    status_label = (
                        f"Crash / Restart Berulang ({crashes}x/{window_min}m, Exit Code {exit_code})"
                    )
                    reason = (
                        f"Container mengalami kegagalan berulang (ExitCode={exit_code}, "
                        f"RestartCount={restart_count})."
                    )
                else:
                    status_label = f"Crash / Gagal Berjalan (Exit Code {exit_code})"
                    reason = f"Container berhenti dengan exit code non-zero ({exit_code})."

                if state_error:
                    reason += f" Error Docker: {state_error}."

                raw_logs = self.backend.tail_logs(
                    cid or container_name, self.config.log_lines
                )
                clean_logs = (
                    sanitize_text(raw_logs, max_length=1200) if raw_logs else None
                )
                alert = ContainerAlert(
                    container_name=container_name,
                    service_name=service_name,
                    status_category="CRASH_RESTART",
                    status_label=status_label,
                    occurred_at=occurred_at,
                    reason=reason,
                    log_excerpt=clean_logs,
                )
            elif oneoff:
                alert = ContainerAlert(
                    container_name=container_name,
                    service_name=service_name,
                    status_category="EXITED",
                    status_label="Exited — Proses sekali jalan selesai normal (Exit Code 0)",
                    occurred_at=occurred_at,
                    reason="Container job/migrasi selesai mengeksekusi tugas dengan Exit Code 0.",
                )
            else:
                alert = ContainerAlert(
                    container_name=container_name,
                    service_name=service_name,
                    status_category="DOWN",
                    status_label="Down — Container berhenti (Exit Code 0)",
                    occurred_at=occurred_at,
                    reason="Service container berhenti atau dimatikan (Exit Code 0).",
                )

        if alert is None:
            return None

        should_send, suppressed = self._should_send(
            alert.container_name, alert.status_category
        )
        if not should_send:
            logger.info(
                "Alert %s untuk %s ditahan sementara (cooldown).",
                alert.status_category,
                alert.container_name,
            )
            return None

        final_alert = ContainerAlert(
            container_name=alert.container_name,
            service_name=alert.service_name,
            status_category=alert.status_category,
            status_label=alert.status_label,
            occurred_at=alert.occurred_at,
            reason=alert.reason,
            log_excerpt=alert.log_excerpt,
            suppressed_count=suppressed,
        )
        message_html = format_container_alert_html(self.config, final_alert)
        self.sender(self.config, message_html)
        return final_alert

    def poll_once(self, *, notify_on_startup_baseline: bool = False) -> list[ContainerAlert]:
        """Memeriksa kondisi container saat ini (jaring pengaman jika event daemon terlewat)."""
        alerts: list[ContainerAlert] = []
        now = datetime.now(timezone.utc)
        for info in self.backend.list_containers():
            name = _clean_container_name(str(info.get("Name") or info.get("Id") or ""))
            if not name or not self.matches_filter(name):
                continue

            state = info.get("State") or {}
            status = str(state.get("Status") or "").lower()
            exit_code = int(state.get("ExitCode") or 0)
            restarting = bool(state.get("Restarting", False))
            oom_killed = bool(state.get("OOMKilled", False))
            oneoff = _is_oneoff_or_no_restart(name, {}, info)

            if restarting or oom_killed or (status in {"exited", "dead"} and exit_code != 0):
                category = "CRASH_RESTART"
                label = (
                    f"Crash / Restarting (Status={status}, ExitCode={exit_code})"
                )
                reason = f"Terdeteksi saat polling: status={status}, exit_code={exit_code}, restarting={restarting}."
            elif status == "running":
                category = "UP"
                label = "Up — Container sedang berjalan"
                reason = "Terdeteksi aktif berjalan saat pemeriksaan berkala."
            elif status in {"exited", "created", "paused"}:
                category = "EXITED" if oneoff else "DOWN"
                label = (
                    "Exited — Tugas selesai (Exit Code 0)"
                    if oneoff
                    else f"Down — Container berstatus {status}"
                )
                reason = f"Terdeteksi saat pemeriksaan berkala (status={status}, exit_code={exit_code})."
            else:
                continue

            with self._lock:
                prev = self._last_polled_status.get(name)
                if prev is None and not notify_on_startup_baseline and category in {"UP", "EXITED"}:
                    # Catat baseline sehat saat start tanpa membanjiri Telegram kecuali bermasalah
                    self._last_polled_status[name] = category
                    continue
                if prev == category:
                    continue

            should_send, suppressed = self._should_send(name, category)
            if not should_send:
                continue

            service_name = _extract_service_label(self.config, {}, info, name)
            log_excerpt: str | None = None
            if category == "CRASH_RESTART":
                raw_logs = self.backend.tail_logs(str(info.get("Id") or name), self.config.log_lines)
                log_excerpt = sanitize_text(raw_logs, max_length=1200) if raw_logs else None

            alert = ContainerAlert(
                container_name=name,
                service_name=service_name,
                status_category=category,
                status_label=label,
                occurred_at=now,
                reason=reason,
                log_excerpt=log_excerpt,
                suppressed_count=suppressed,
            )
            message_html = format_container_alert_html(self.config, alert)
            self.sender(self.config, message_html)
            alerts.append(alert)
        return alerts


def _run_test_notification(config: MonitorConfig, dry_run: bool) -> int:
    sim_alert = ContainerAlert(
        container_name="wms_prod_backend",
        service_name=f"backend ({config.app_name}, project: wms)",
        status_category="CRASH_RESTART",
        status_label="Crash / Restart Berulang (2x/5m, Exit Code 1)",
        occurred_at=datetime.now(timezone.utc),
        reason=(
            "Simulasi kegagalan container (contoh koneksi DB postgresql://wms_app:Rahasia99@postgres:5432/wms "
            "harus tersamarkan oleh sanitizer)."
        ),
        log_excerpt=sanitize_text(
            "ERROR: gagal terhubung ke postgresql://wms_owner:SecretPass!@postgres:5432/wms_production\n"
            "Contact admin admin@jejakstok.site | token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.sig123456"
        ),
    )
    html_msg = format_container_alert_html(config, sim_alert, is_test=True)
    if dry_run:
        print("=== DRY RUN TELEGRAM PAYLOAD ===")
        print(html_msg)
        return 0

    ok = send_telegram_html(config, html_msg)
    if ok:
        print("Berhasil mengirim simulasi notifikasi status container Docker ke Telegram.")
        return 0
    print("Gagal mengirim simulasi notifikasi status container Docker ke Telegram.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pemantau status container Docker real-time dengan notifikasi Telegram."
    )
    parser.add_argument(
        "--env-file",
        help="Path berkas .env eksplisit (mis. /opt/wms/.env.production).",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "cli", "socket"),
        default="auto",
        help="Cara membaca event Docker (default: auto).",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Kirim satu notifikasi simulasi status container lalu keluar.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Periksa status container aktif sekali lalu keluar.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Cetak pesan Telegram ke stdout tanpa mengirim ke API Telegram.",
    )
    args = parser.parse_args(argv)

    load_env_defaults(args.env_file)
    config = MonitorConfig.from_env()

    if args.test:
        return _run_test_notification(config, dry_run=args.dry_run)

    if not args.dry_run and (not config.enabled or not config.has_valid_telegram_credentials()):
        logger.error(
            "Telegram monitor tidak aktif atau TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diatur."
        )
        return 1

    backend = select_docker_backend(args.backend, config.socket_path)
    sender: Callable[[MonitorConfig, str], bool] = (
        (lambda _cfg, text: (print(f"--- DRY RUN ---\n{text}\n"), True)[1])
        if args.dry_run
        else send_telegram_html
    )
    engine = DockerMonitorEngine(config, backend, sender=sender)

    if args.once:
        alerts = engine.poll_once(notify_on_startup_baseline=True)
        logger.info("Pemeriksaan --once selesai (%s notifikasi dikirim).", len(alerts))
        return 0

    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Menerima sinyal berhenti (%s), menghentikan monitor...", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    def _poll_loop() -> None:
        while not stop_event.wait(config.poll_interval_seconds):
            try:
                engine.poll_once()
            except Exception as poll_exc:
                logger.warning("Gagal polling berkala Docker: %s", poll_exc)

    # Catat baseline container berjalan + langsung peringatkan bila ada container yang sudah crash saat startup
    engine.poll_once(notify_on_startup_baseline=False)

    poller = threading.Thread(target=_poll_loop, daemon=True)
    poller.start()

    logger.info(
        "Docker Telegram Monitor berjalan (env=%s, backend=%s, filters=%s).",
        config.environment,
        type(backend).__name__,
        ",".join(config.filters) if config.filters else "*",
    )

    backoff = 1.0
    while not stop_event.is_set():
        try:
            for event in backend.stream_events():
                if stop_event.is_set():
                    break
                engine.process_event(event)
                backoff = 1.0
        except Exception as stream_exc:
            if stop_event.is_set():
                break
            logger.warning(
                "Stream event Docker terputus (%s); mencoba sambung ulang dalam %.0fs...",
                sanitize_text(str(stream_exc), max_length=200),
                backoff,
            )
            stop_event.wait(backoff)
            backoff = min(30.0, backoff * 2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
