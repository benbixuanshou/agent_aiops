"""HTTP endpoint tests — auth, rate limiting, health, templates."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestHealth:
    def test_health_no_auth_required(self, client):
        r = client.get("/milvus/health")
        assert r.status_code == 200
        data = r.json()
        assert "milvus" in data
        assert "deepseek" in data


class TestAuth:
    def test_no_key_returns_401(self, client, monkeypatch):
        monkeypatch.setattr("app.middleware.auth._parse_keys", lambda _: {"test-key"})
        r = client.post("/api/chat", json={"Id": "", "Question": "hello"})
        assert r.status_code == 401

    def test_invalid_key_returns_401(self, client, monkeypatch):
        monkeypatch.setattr("app.middleware.auth._parse_keys", lambda _: {"test-key"})
        r = client.post(
            "/api/chat",
            json={"Id": "", "Question": "hello"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert r.status_code == 401

    def test_health_skips_auth(self, client, monkeypatch):
        monkeypatch.setattr("app.middleware.auth._parse_keys", lambda _: {"test-key"})
        r = client.get("/milvus/health")
        assert r.status_code == 200


class TestTemplates:
    def test_list_templates(self, client):
        r = client.get("/api/ai_ops/templates")
        assert r.status_code == 200
        templates = r.json()
        assert len(templates) >= 4
        for t in templates:
            assert "key" in t
            assert "label" in t
            assert "severity" in t


class TestSession:
    def test_clear_session(self, client):
        r = client.post("/api/chat/clear", json={"Id": "test-session"})
        assert r.status_code == 200
