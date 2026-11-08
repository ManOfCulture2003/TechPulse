"""Exercise the real auth boundary with independent clients, not mocked guards."""
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

KEY = "test-only-key-" + "x" * 32


@pytest.fixture
def secured(tmp_path):
    return create_app(tmp_path / "private.sqlite", collect=False, access_key=KEY)


def test_private_endpoints_need_login_and_other_client_cannot_read(secured):
    with TestClient(secured, base_url="http://localhost") as owner, TestClient(secured, base_url="http://localhost") as stranger:
        for route in ("/api/overview", "/api/processes", "/api/export.csv", "/api/diagnostics.json", "/api/docs", "/openapi.json"):
            assert stranger.get(route).status_code == 401
        assert "Unlock this app" in owner.get("/").text
        assert KEY not in owner.get("/").text
        response = owner.post("/auth/login", json={"key": KEY})
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        assert owner.get("/api/overview").status_code == 200
        assert stranger.get("/api/overview").status_code == 401
        cookie = owner.cookies.get(secured.state.access.cookie)
        assert owner.post("/auth/logout").status_code == 200
        assert owner.get("/api/overview", headers={"cookie": f"{secured.state.access.cookie}={cookie}"}).status_code == 401


@pytest.mark.parametrize("value", [{}, {"key": None}, {"key": 12}, {"key": ""}, {"key": "x"*257}, {"key": KEY, "admin": True}, []])
def test_incomplete_or_wrong_shape_rejected(secured, value):
    with TestClient(secured, base_url="http://localhost") as client:
        assert client.post("/auth/login", json=value).status_code == 400
        assert client.get("/api/overview").status_code == 401


def test_expiry_throttle_and_cross_origin(secured):
    clock = [100.0]
    secured.state.access.clock = lambda: clock[0]
    with TestClient(secured, base_url="http://localhost") as client:
        assert client.post("/auth/login", json={"key": KEY}, headers={"Origin":"http://localhost:9999"}).status_code == 403
        assert client.post("/auth/login", content="x"*5000, headers={"Content-Type":"application/json"}).status_code == 413
        assert client.post("/auth/login", content="bad", headers={"Content-Type":"application/json"}).status_code == 400
        for _ in range(5):
            assert client.post("/auth/login", json={"key":"wrong"}).status_code == 401
        assert client.post("/auth/login", json={"key":KEY}).status_code == 429
        clock[0] += 31
        assert client.post("/auth/login", json={"key":KEY}).status_code == 200
        assert client.get("/api/overview", headers={"Origin":"https://evil.invalid"}).status_code == 403
        clock[0] += 28801
        assert client.get("/api/overview").status_code == 401


def test_session_not_valid_in_another_app(secured, tmp_path):
    other = create_app(tmp_path / "other.sqlite", collect=False, access_key=KEY)
    with TestClient(secured, base_url="http://localhost") as first, TestClient(other, base_url="http://localhost") as second:
        first.post("/auth/login", json={"key":KEY})
        second.cookies.update(first.cookies)
        assert second.get("/api/overview").status_code == 401
