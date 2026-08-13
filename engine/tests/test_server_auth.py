"""Auth and header behaviour for the local event channel."""

from __future__ import annotations

from fastapi.testclient import TestClient

from antivenom.config import reset_caches
from antivenom.server.events import create_app, serve


def test_health_is_open_and_carries_security_headers() -> None:
    client = TestClient(create_app(api_token="secret"))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["auth_required"] is True
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_api_requires_bearer_when_token_configured() -> None:
    client = TestClient(create_app(api_token="secret"))
    denied = client.get("/api/history")
    assert denied.status_code == 401
    allowed = client.get("/api/history", headers={"Authorization": "Bearer secret"})
    assert allowed.status_code == 200
    assert "events" in allowed.json()


def test_serve_refuses_off_loopback_without_token(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ANTIVENOM_HOST", "0.0.0.0")
    monkeypatch.delenv("ANTIVENOM_API_TOKEN", raising=False)
    reset_caches()
    try:
        serve()
        raise AssertionError("serve() should have refused off-loopback without a token")
    except SystemExit as exc:
        assert "ANTIVENOM_API_TOKEN" in str(exc)
    finally:
        reset_caches()
