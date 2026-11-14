"""Pengujian pemantau status container Docker -> Telegram (Tahap 13 / Poin 7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from scripts import docker_telegram_monitor as dtm


def _make_config(
    *,
    cooldown_seconds: int = 0,
    crash_threshold: int = 2,
    filters: tuple[str, ...] = ("wms",),
) -> dtm.MonitorConfig:
    return dtm.MonitorConfig(
        enabled=True,
        bot_token="9237000001:AAFakeDockerMonitorToken1234567890",
        chat_id="999999999",
        thread_id=None,
        app_name="JejakStok WMS",
        environment="production",
        host_label="vps-wms-prod",
        filters=filters,
        cooldown_seconds=cooldown_seconds,
        crash_window_seconds=300,
        crash_threshold=crash_threshold,
        poll_interval_seconds=30,
        log_lines=10,
        socket_path="/var/run/docker.sock",
        timeout_seconds=5.0,
    )


class FakeDockerBackend:
    """Backend palsu untuk mensimulasikan inspect container, daftar container, dan tail log."""

    def __init__(
        self,
        inspect_map: dict[str, dict[str, Any]] | None = None,
        logs_map: dict[str, str] | None = None,
    ) -> None:
        self.inspect_map = inspect_map or {}
        self.logs_map = logs_map or {}

    def stream_events(self) -> Iterator[dict[str, Any]]:
        return iter(())

    def inspect_container(self, container_id: str) -> dict[str, Any] | None:
        return self.inspect_map.get(container_id)

    def list_containers(self) -> list[dict[str, Any]]:
        return list(self.inspect_map.values())

    def tail_logs(self, container_id: str, _tail: int) -> str:
        return self.logs_map.get(container_id, "")


def _inspect_payload(
    name: str,
    *,
    service: str,
    status: str = "running",
    exit_code: int = 0,
    oom_killed: bool = False,
    restart_count: int = 0,
    restart_policy: str = "always",
    oneoff: bool = False,
    error: str = "",
) -> dict[str, Any]:
    return {
        "Id": name,
        "Name": f"/{name}",
        "Config": {
            "Image": "ghcr.io/rayhanyl/api_warehouse_app/wms-backend:latest",
            "Labels": {
                "com.docker.compose.service": service,
                "com.docker.compose.project": "wms",
                "com.docker.compose.oneoff": "True" if oneoff else "False",
            },
        },
        "HostConfig": {"RestartPolicy": {"Name": restart_policy}},
        "RestartCount": restart_count,
        "State": {
            "Status": status,
            "ExitCode": exit_code,
            "OOMKilled": oom_killed,
            "Error": error,
            "Health": {"Log": [{"Output": "HTTP 500 Internal Error"}]},
        },
    }


def test_docker_monitor_handles_up_down_exited_and_healthcheck_events() -> None:
    backend = FakeDockerBackend(
        inspect_map={
            "wms_prod_backend": _inspect_payload("wms_prod_backend", service="backend"),
            "wms_prod_migration": _inspect_payload(
                "wms_prod_migration",
                service="backend-migration",
                restart_policy="no",
                oneoff=True,
            ),
            "unrelated_redis": _inspect_payload("unrelated_redis", service="redis"),
        }
    )
    sent_messages: list[str] = []
    engine = dtm.DockerMonitorEngine(
        _make_config(),
        backend,
        sender=lambda _cfg, html_text: (sent_messages.append(html_text), True)[1],
    )

    # 1. Container di luar filter diabaikan
    ignored = engine.process_event(
        {
            "Action": "start",
            "time": 1794648200,
            "Actor": {"ID": "unrelated_redis", "Attributes": {"name": "unrelated_redis"}},
        }
    )
    assert ignored is None

    # 2. Up
    up_alert = engine.process_event(
        {
            "Action": "start",
            "time": 1794648210,
            "Actor": {"ID": "wms_prod_backend", "Attributes": {"name": "wms_prod_backend"}},
        }
    )
    assert up_alert is not None
    assert up_alert.status_category == "UP"

    # 3. Down (service berhenti dengan exit 0)
    down_alert = engine.process_event(
        {
            "Action": "die",
            "time": 1794648220,
            "Actor": {
                "ID": "wms_prod_backend",
                "Attributes": {"name": "wms_prod_backend", "exitCode": "0"},
            },
        }
    )
    assert down_alert is not None
    assert down_alert.status_category == "DOWN"

    # 4. Exited (container one-off / migrasi selesai normal exit 0)
    exited_alert = engine.process_event(
        {
            "Action": "die",
            "time": 1794648230,
            "Actor": {
                "ID": "wms_prod_migration",
                "Attributes": {"name": "wms_prod_migration", "exitCode": "0"},
            },
        }
    )
    assert exited_alert is not None
    assert exited_alert.status_category == "EXITED"

    # 5. Unhealthy & Healthy
    unhealthy_alert = engine.process_event(
        {
            "Action": "health_status: unhealthy",
            "time": 1794648240,
            "Actor": {"ID": "wms_prod_backend", "Attributes": {"name": "wms_prod_backend"}},
        }
    )
    assert unhealthy_alert is not None
    assert unhealthy_alert.status_category == "UNHEALTHY"
    assert "HTTP 500 Internal Error" in sent_messages[-1]

    healthy_alert = engine.process_event(
        {
            "Action": "health_status: healthy",
            "time": 1794648250,
            "Actor": {"ID": "wms_prod_backend", "Attributes": {"name": "wms_prod_backend"}},
        }
    )
    assert healthy_alert is not None
    assert healthy_alert.status_category == "UP"
    assert len(sent_messages) == 5


def test_docker_monitor_detects_crash_oom_sanitizes_logs_and_throttles_crash_loop() -> None:
    backend = FakeDockerBackend(
        inspect_map={
            "wms_prod_backend": _inspect_payload(
                "wms_prod_backend",
                service="backend",
                status="exited",
                exit_code=1,
                restart_count=2,
            ),
            "wms_prod_postgres": _inspect_payload(
                "wms_prod_postgres",
                service="postgres",
                status="exited",
                exit_code=137,
                oom_killed=True,
            ),
        },
        logs_map={
            "wms_prod_backend": (
                "FATAL: koneksi postgresql://wms_owner:SecretProdPass!@postgres:5432/wms_production ditolak\n"
                "User email: operator@jejakstok.site | token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.abc123456"
            )
        },
    )
    sent_messages: list[str] = []
    engine = dtm.DockerMonitorEngine(
        _make_config(cooldown_seconds=60, crash_threshold=2),
        backend,
        sender=lambda _cfg, html_text: (sent_messages.append(html_text), True)[1],
    )

    # 1. Crash pertama mengirim alert segera + log tersanitasi
    crash1 = engine.process_event(
        {
            "Action": "die",
            "time": 1794648300,
            "Actor": {
                "ID": "wms_prod_backend",
                "Attributes": {"name": "wms_prod_backend", "exitCode": "1"},
            },
        }
    )
    assert crash1 is not None
    assert crash1.status_category == "CRASH_RESTART"
    msg1 = sent_messages[-1]
    assert "wms_prod_backend" in msg1
    assert "backend" in msg1
    assert "SecretProdPass!" not in msg1
    assert "operator@jejakstok.site" not in msg1
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in msg1
    assert "[REDACTED]" in msg1

    # 2. Recovery start pertama diizinkan (< threshold)
    rec1 = engine.process_event(
        {
            "Action": "start",
            "time": 1794648302,
            "Actor": {"ID": "wms_prod_backend", "Attributes": {"name": "wms_prod_backend"}},
        }
    )
    assert rec1 is not None and rec1.status_category == "UP"

    # 3. Crash kedua menembus crash_threshold=2 -> eskalasi Crash/Restart Berulang langsung terkirim
    crash2 = engine.process_event(
        {
            "Action": "die",
            "time": 1794648304,
            "Actor": {
                "ID": "wms_prod_backend",
                "Attributes": {"name": "wms_prod_backend", "exitCode": "1"},
            },
        }
    )
    assert crash2 is not None
    assert "Berulang" in crash2.status_label

    # 4. Flapping start/die berikutnya di dalam cooldown 60s ditahan agar bot tidak terkena rate limit 429
    flapping_start = engine.process_event(
        {
            "Action": "start",
            "time": 1794648305,
            "Actor": {"ID": "wms_prod_backend", "Attributes": {"name": "wms_prod_backend"}},
        }
    )
    flapping_die = engine.process_event(
        {
            "Action": "die",
            "time": 1794648306,
            "Actor": {
                "ID": "wms_prod_backend",
                "Attributes": {"name": "wms_prod_backend", "exitCode": "1"},
            },
        }
    )
    assert flapping_start is None
    assert flapping_die is None

    # 5. Container berbeda (OOMKilled) tetap dilaporkan segera
    oom_alert = engine.process_event(
        {
            "Action": "die",
            "time": 1794648310,
            "Actor": {
                "ID": "wms_prod_postgres",
                "Attributes": {"name": "wms_prod_postgres", "exitCode": "137"},
            },
        }
    )
    assert oom_alert is not None
    assert "OOMKilled" in oom_alert.status_label


def test_docker_monitor_poll_once_stream_decoder_and_bom_env(tmp_path: Path) -> None:
    backend = FakeDockerBackend(
        inspect_map={
            "wms_prod_backend": _inspect_payload(
                "wms_prod_backend", service="backend", status="running"
            ),
            "wms_prod_postgres": _inspect_payload(
                "wms_prod_postgres", service="postgres", status="exited", exit_code=137
            ),
        },
        logs_map={"wms_prod_postgres": "OOM failure"},
    )
    sent: list[str] = []
    engine = dtm.DockerMonitorEngine(
        _make_config(),
        backend,
        sender=lambda _cfg, text: (sent.append(text), True)[1],
    )

    # Saat startup baseline, hanya container bermasalah yang dikirim
    startup_alerts = engine.poll_once(notify_on_startup_baseline=False)
    assert len(startup_alerts) == 1
    assert startup_alerts[0].container_name == "wms_prod_postgres"

    # Dekoder frame multiplexed 8-byte Docker
    payload = b"hello crash log\n"
    header = b"\x02\x00\x00\x00" + len(payload).to_bytes(4, "big")
    assert dtm._decode_docker_log_stream(header + payload) == "hello crash log"

    # Parsing .env ber-BOM UTF-8
    env_file = tmp_path / "bom.env"
    env_file.write_text('TELEGRAM_ENABLED="true"\nTELEGRAM_CHAT_ID=999999999\n', encoding="utf-8-sig")
    parsed = dtm._parse_env_file(env_file)
    assert parsed == {"TELEGRAM_ENABLED": "true", "TELEGRAM_CHAT_ID": "999999999"}
