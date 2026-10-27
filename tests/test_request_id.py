"""Pengerasan korelasi request untuk log operasional (PRD 7.6)."""

import uuid


def test_request_id_preserves_safe_value_and_replaces_invalid_value(client):
    safe_request_id = "wms-request:20261023.1"

    safe_response = client.get("/health", headers={"X-Request-ID": safe_request_id})
    assert safe_response.status_code == 200
    assert safe_response.headers["X-Request-ID"] == safe_request_id

    invalid_response = client.get("/health", headers={"X-Request-ID": "bad value"})
    assert invalid_response.status_code == 200
    generated_request_id = invalid_response.headers["X-Request-ID"]
    assert generated_request_id != "bad value"
    assert str(uuid.UUID(generated_request_id)) == generated_request_id

    oversized_response = client.get("/health", headers={"X-Request-ID": "x" * 129})
    assert oversized_response.status_code == 200
    assert oversized_response.headers["X-Request-ID"] != "x" * 129


def test_cors_allows_frontend_origin_and_required_headers(client):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": (
                "Authorization, Content-Type, X-Request-ID"
            ),
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Access-Control-Allow-Credentials" not in response.headers
    assert "X-Request-ID" in response.headers["Access-Control-Allow-Headers"]

    actual_response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert actual_response.status_code == 200
    assert actual_response.headers["Access-Control-Expose-Headers"] == "X-Request-ID"


def test_cors_allows_loopback_frontend_origin(client):
    response = client.options(
        "/api/v1/auth/refresh",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5173"
