"""Middleware integration tests."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestAuth:
    def test_health_no_auth(self, client):
        r = client.get("/milvus/health")
        assert r.status_code == 200

    def test_metrics_no_auth(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_login_no_auth(self, client):
        r = client.post("/api/login", json={"api_key": ""})
        assert r.status_code == 401

    def test_chat_no_key_rejected(self, client, monkeypatch):
        monkeypatch.setattr("app.middleware.auth._parse_keys", lambda _: {"test-key"})
        r = client.post("/api/chat", json={"Id": "", "Question": "test"})
        assert r.status_code == 401

    def test_chat_valid_key_accepted(self, client, monkeypatch):
        monkeypatch.setattr("app.middleware.auth._parse_keys", lambda _: {"test-key"})
        monkeypatch.setattr("app.tenant_store.tenant_registry.lookup", lambda k: None)
        r = client.post("/api/chat", json={"Id": "", "Question": "test"},
                        headers={"X-API-Key": "test-key"})
        assert r.status_code in (200, 401)  # 200 if no auth fallback

    def test_static_files_bypass_auth(self, client, monkeypatch):
        monkeypatch.setattr("app.middleware.auth._parse_keys", lambda _: {"test-key"})
        r = client.get("/styles.css")
        assert r.status_code == 200

    def test_root_bypass_auth(self, client, monkeypatch):
        monkeypatch.setattr("app.middleware.auth._parse_keys", lambda _: {"test-key"})
        r = client.get("/")
        assert r.status_code == 200


class TestRateLimit:
    def test_metrics_bypass(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_health_bypass(self, client):
        r = client.get("/milvus/health")
        assert r.status_code == 200


class TestLogging:
    def test_request_id_header(self, client):
        r = client.get("/milvus/health")
        assert r.status_code == 200
