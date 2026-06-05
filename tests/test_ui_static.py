"""Phase 6 — static UI served from FastAPI."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_ui_index_served() -> None:
    client = TestClient(create_app())
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Groww Chatbot" in resp.text
    assert "/assets/groww-logo.png" in resp.text
    assert "chat-list" in resp.text
    assert "new-chat-primary" in resp.text
    assert "sidebar-backdrop" in resp.text
    assert "Supported funds" in resp.text
    assert "/config.js" in resp.text
    assert "/app.js" in resp.text


def test_ui_assets() -> None:
    client = TestClient(create_app())
    assert client.get("/styles.css").status_code == 200
    assert client.get("/config.js").status_code == 200
    assert client.get("/app.js").status_code == 200
    assert client.get("/assets/groww-logo.png").status_code == 200


def test_api_still_available_with_ui_mount() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/schemes")
    assert resp.status_code == 200
    assert len(resp.json()["schemes"]) == 5
