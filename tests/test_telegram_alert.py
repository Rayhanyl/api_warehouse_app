"""Pengujian unit & integrasi notifikasi error real-time Telegram & sanitasi sensitif (Tahap 13 / Poin 6)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi.testclient import TestClient
import httpx
import pytest
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core import telegram_alert
from app.core.config import Settings, settings
from app.core.exceptions import ValidationDomainError
from app.core.sanitizer import (
    is_sensitive_key,
    sanitize_mapping,
    sanitize_text,
    sanitize_url_path_and_query,
)
from app.main import create_app


def test_sanitizer_redacts_secrets_tokens_and_pii() -> None:
    raw = (
        "Gagal koneksi postgresql://wms_owner:SuperSecret!#@db.internal:5432/wms_prod | "
        "URL https://api.telegram.org/bot1111111111:AAFakeDummyBotToken00000000000000000/sendMessage | "
        "token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.abc123456789 | "
        '{"password": "RahasiaUser!", "refresh_token": "tok_xyz"} | '
        "DETAIL: Key (email)=(rayhan@contoh.co.id) already exists. | "
        "Kontak: admin@contoh.id | "
        "HP: +6281234567890 / 081987654321 | Trace: trace-uuid-1234 | Status: 500"
    )
    cleaned = sanitize_text(raw)

    assert "[REDACTED]]" not in cleaned

    assert "SuperSecret!#" not in cleaned
    assert "AAFakeDummyBotToken00000000000000000" not in cleaned
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in cleaned
    assert "RahasiaUser!" not in cleaned
    assert "tok_xyz" not in cleaned
    assert "rayhan@contoh.co.id" not in cleaned
    assert "admin@contoh.id" not in cleaned
    assert "81234567890" not in cleaned
    assert "081987654321" not in cleaned

    # Informasi teknis non-sensitif wajib tetap terbaca
    assert "db.internal:5432/wms_prod" in cleaned
    assert "trace-uuid-1234" in cleaned
    assert "Status: 500" in cleaned
    assert "[REDACTED]" in cleaned
    assert "[REDACTED_BOT_TOKEN]" in cleaned
    assert "[REDACTED_EMAIL]" in cleaned
    assert "[REDACTED_PHONE]" in cleaned


def test_sanitizer_cleans_query_params_and_mappings() -> None:
    assert is_sensitive_key("access_token") is True
    assert is_sensitive_key("user_email") is True
    assert is_sensitive_key("warehouse_id") is False

    clean_url = sanitize_url_path_and_query(
        "/api/v1/users/operator@wms.id",
        "token=secret123&password=pw1&warehouse_id=2&q=test%40example.com",
    )
    assert "secret123" not in clean_url
    assert "pw1" not in clean_url
    assert "operator@wms.id" not in clean_url
    assert "test@example.com" not in clean_url
    assert "warehouse_id=2" in clean_url
    assert "token=[REDACTED]" in clean_url

    nested = sanitize_mapping(
        {
            "password": "abc",
            "profile": {"no_hp": "08123456789", "role": "Super Admin"},
        }
    )
    assert nested == {
        "password": "[REDACTED]",
        "profile": {"no_hp": "[REDACTED]", "role": "Super Admin"},
    }


def test_telegram_settings_accepts_blank_optional_fields_and_blocks_placeholders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed = Settings(
        _env_file=None,
        database_url="postgresql://wms_app:pw@localhost:5432/wms",
        jwt_secret="x" * 40,
        telegram_enabled=True,
        telegram_bot_token="",
        telegram_chat_id="",
        telegram_thread_id="",
    )
    assert parsed.telegram_thread_id is None
    assert parsed.telegram_bot_token is None

    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "<ganti-dengan-token>")
    monkeypatch.setattr(settings, "telegram_chat_id", "999999999")
    assert telegram_alert.is_telegram_configured() is False

    monkeypatch.setattr(
        settings, "telegram_bot_token", "9237000000:AAFakeTokenForUnitTestValidation000"
    )
    assert telegram_alert.is_telegram_configured() is True


@pytest.mark.anyio
async def test_dispatch_error_alert_formats_required_fields_and_hides_token_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_token = "9237000001:AAFakeUnitTestBotToken1234567890abc"
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", fake_token)
    monkeypatch.setattr(settings, "telegram_chat_id", "999999999")
    monkeypatch.setattr(settings, "telegram_thread_id", 42)
    monkeypatch.setattr(settings, "telegram_cooldown_seconds", 0)
    monkeypatch.setattr(settings, "app_env", "staging")

    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    def _helper_inner_failure() -> None:
        raise ValueError("Koneksi gagal ke postgresql://u:Pass123@db:5432/wms" + ("!" * 5000))

    try:
        _helper_inner_failure()
    except ValueError as err:
        ctx = telegram_alert.build_error_alert_context(
            err,
            trace_id="req-trace-abc-999",
            http_status=500,
            source="POST /api/v1/goods-receipts?token=secret",
        )

    ok = await telegram_alert.dispatch_error_alert_async(
        ctx, transport=httpx.MockTransport(handler)
    )
    assert ok is True
    assert len(captured) == 1

    body = captured[0]
    assert body["chat_id"] == "999999999"
    assert body["message_thread_id"] == 42
    assert body["parse_mode"] == "HTML"
    text = body["text"]
    assert len(text) <= 4096
    assert "WMS REST API" in text
    assert "STAGING" in text
    assert "ValueError" in text
    assert "req-trace-abc-999" in text
    assert "test_telegram_alert.py" in text
    assert "_helper_inner_failure" in text
    assert "WIB" in text
    assert "Pass123" not in text
    assert "secret" not in text

    # Pastikan kegagalan HTTP API Telegram tidak melempar exception maupun membocorkan bot token di log
    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"Connect error calling {request.url}", request=request)

    with caplog.at_level(logging.WARNING, logger="wms"):
        ok_fail = await telegram_alert.dispatch_error_alert_async(
            ctx, transport=httpx.MockTransport(failing_handler)
        )
    assert ok_fail is False
    assert fake_token not in caplog.text


@pytest.mark.anyio
async def test_telegram_cooldown_deduplication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(
        settings, "telegram_bot_token", "9237000001:AAFakeUnitTestBotToken1234567890abc"
    )
    monkeypatch.setattr(settings, "telegram_chat_id", "999999999")
    monkeypatch.setattr(settings, "telegram_cooldown_seconds", 60)

    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content.decode("utf-8"))["text"])
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    try:
        raise RuntimeError("Error berulang")
    except RuntimeError as exc:
        ctx = telegram_alert.build_error_alert_context(
            exc, trace_id="trace-1", source="GET /api/v1/items"
        )

    assert await telegram_alert.dispatch_error_alert_async(ctx, transport=transport) is True
    assert await telegram_alert.dispatch_error_alert_async(ctx, transport=transport) is False
    assert len(sent) == 1


def test_fastapi_500_and_http5xx_notify_telegram_while_domain_errors_do_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(
        settings, "telegram_bot_token", "9237000001:AAFakeUnitTestBotToken1234567890abc"
    )
    monkeypatch.setattr(settings, "telegram_chat_id", "999999999")
    monkeypatch.setattr(settings, "telegram_cooldown_seconds", 0)

    dispatched: list[telegram_alert.ErrorAlertContext] = []

    async def fake_dispatch(ctx: telegram_alert.ErrorAlertContext, **_kwargs: Any) -> bool:
        dispatched.append(ctx)
        return True

    monkeypatch.setattr(telegram_alert, "dispatch_error_alert_async", fake_dispatch)

    test_app = create_app()

    @test_app.get("/__test/domain-error")
    def raise_domain() -> None:
        raise ValidationDomainError("Input salah")

    @test_app.get("/__test/http-503")
    def raise_http_503() -> None:
        raise StarletteHTTPException(status_code=503, detail="Maintenance")

    @test_app.get("/__test/crash")
    def raise_crash() -> None:
        raise RuntimeError("Ledakan internal user@example.com password=secret_pw")

    client = TestClient(test_app, raise_server_exceptions=False)

    # 1. DomainError (422) & 404 tidak boleh memicu alert Telegram
    r_dom = client.get("/__test/domain-error", headers={"X-Request-ID": "trace-dom-1"})
    assert r_dom.status_code == 422
    r_404 = client.get("/__test/tidak-ada", headers={"X-Request-ID": "trace-404-1"})
    assert r_404.status_code == 404
    assert dispatched == []

    # 2. HTTP 500 internal error memicu BackgroundTask Telegram + menjaga X-Request-ID
    r_500 = client.get(
        "/__test/crash?token=rahasia&page=1",
        headers={"X-Request-ID": "trace-crash-500"},
    )
    assert r_500.status_code == 500
    assert r_500.headers.get("X-Request-ID") == "trace-crash-500"
    assert r_500.json()["error"]["code"] == "INTERNAL_ERROR"
    assert len(dispatched) == 1
    ctx_500 = dispatched[0]
    assert ctx_500.trace_id == "trace-crash-500"
    assert ctx_500.error_type == "RuntimeError"
    assert ctx_500.endpoint == "GET /__test/crash?token=[REDACTED]&page=1"
    assert "secret_pw" not in ctx_500.error_message
    assert "user@example.com" not in ctx_500.error_message
    assert ctx_500.app_location is not None

    # 3. Starlette HTTPException >= 500 juga memicu alert
    r_503 = client.get("/__test/http-503", headers={"X-Request-ID": "trace-503-1"})
    assert r_503.status_code == 503
    assert len(dispatched) == 2
    assert dispatched[1].http_status == 503
    assert dispatched[1].trace_id == "trace-503-1"


@pytest.mark.anyio
async def test_lifespan_startup_db_failure_notifies_telegram(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import database
    from app.main import lifespan

    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(
        settings, "telegram_bot_token", "9237000001:AAFakeUnitTestBotToken1234567890abc"
    )
    monkeypatch.setattr(settings, "telegram_chat_id", "999999999")
    monkeypatch.setattr(settings, "telegram_cooldown_seconds", 0)

    captured: list[telegram_alert.ErrorAlertContext] = []

    async def fake_dispatch(ctx: telegram_alert.ErrorAlertContext, **_kwargs: Any) -> bool:
        captured.append(ctx)
        return True

    def fail_open_pool() -> None:
        raise RuntimeError(
            "Database mati postgresql://wms_owner:RahasiaPool!@postgres:5432/wms_prod"
        )

    monkeypatch.setattr(telegram_alert, "dispatch_error_alert_async", fake_dispatch)
    monkeypatch.setattr(database, "open_pool", fail_open_pool)

    test_app = create_app()
    with pytest.raises(RuntimeError, match="Database mati"):
        async with lifespan(test_app):
            pass

    assert len(captured) == 1
    assert captured[0].endpoint == "lifespan/startup (database.open_pool)"
    assert "RahasiaPool!" not in captured[0].error_message
