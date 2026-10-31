from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.monitor import Monitor, compute_alerts
from app.storage import HistoryStore
from app.windows_events import read_failed_logins


def sample(timestamp=None, **kw):
    row = dict(timestamp=timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        cpu_percent=26.1, memory_percent=42.0, disk_percent=63.0,
        memory_used_gb=8.2, memory_total_gb=16.0, disk_free_gb=110.0,
        disk_total_gb=300.0, network_up_bps=300, network_down_bps=9500)
    row.update(kw)
    return row


def test_health_and_home(tmp_path):
    with TestClient(create_app(tmp_path / "app.sqlite", collect=False), base_url="http://localhost") as client:
        health = client.get("/api/health").json()
        assert health["local_only"] is True
        assert health["collector"]["state"] == "disabled"
        assert "TechPulse" in client.get("/").text
        assert client.get("/api/overview").json()["sample"] is None


def test_robots_cannot_change_metrics(tmp_path):
    with TestClient(create_app(tmp_path / "app.sqlite", collect=False), base_url="http://localhost") as client:
        assert client.post("/api/overview").status_code == 405
        assert client.get("/api/history?minutes=0").status_code == 422
        assert client.get("/api/history?minutes=100000").status_code == 422
        assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 400


def test_history_round_trip_csv(tmp_path):
    db = tmp_path / "app.sqlite"
    store = HistoryStore(db)
    store.add(sample())
    with TestClient(create_app(db, collect=False), base_url="http://localhost") as client:
        o = client.get("/api/overview").json()
        assert o["sample"]["cpu_percent"] == 26.1
        assert len(client.get("/api/history").json()["points"]) == 1
        content = client.get("/api/export.csv").text
        assert "cpu_percent" in content and "26.1" in content


def test_alert_boundaries():
    assert compute_alerts(sample()) == []
    alert = compute_alerts(sample(cpu_percent=90, memory_percent=86, disk_percent=92))
    assert {a["code"] for a in alert} == {"cpu_percent", "memory_percent", "disk_percent"}


def test_monitor_has_nonnegative_measurements():
    m = Monitor()
    m.prime()
    result = m.sample()
    assert 0 <= result["memory_percent"] <= 100
    assert result["disk_total_gb"] >= result["disk_free_gb"] >= 0
    assert result["network_down_bps"] >= 0


def test_security_response_safe_shape():
    result = read_failed_logins()
    assert set(result.keys()) == {"status", "message", "events"}
    assert isinstance(result["events"], list)

def test_overview_discloses_stale_values_without_live_alerts(tmp_path):
    db = tmp_path / "stale.sqlite"
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(timespec="seconds")
    HistoryStore(db).add(sample(timestamp=old, cpu_percent=99))
    with TestClient(create_app(db, collect=False, interval=15), base_url="http://localhost") as client:
        result = client.get("/api/overview").json()
        assert result["sample"]["cpu_percent"] == 99
        assert result["collection"]["state"] == "stale"
        assert result["collection"]["age_seconds"] >= 590
        assert result["alerts"] == []


def test_recent_database_row_does_not_imply_live_collection(tmp_path):
    db = tmp_path / "fresh.sqlite"
    HistoryStore(db).add(sample(cpu_percent=99))
    with TestClient(create_app(db, collect=False, interval=15), base_url="http://localhost") as client:
        result = client.get("/api/overview").json()
        assert result["collection"]["state"] == "fresh"
        assert result["collector"]["state"] == "disabled"
        assert result["alerts"] == []


def test_live_collector_allows_current_threshold_alerts(tmp_path):
    db = tmp_path / "running.sqlite"
    HistoryStore(db).add(sample(cpu_percent=99))
    with TestClient(create_app(db, collect=False, interval=15), base_url="http://localhost") as client:
        # Simulate a successful collection without starting the background worker.
        client.app.state.collector_status.succeeded()
        result = client.get("/api/overview").json()
        assert result["collector"]["state"] == "running"
        assert result["alerts"][0]["code"] == "cpu_percent"


def test_collector_failure_suppresses_recent_threshold_alerts(tmp_path):
    db = tmp_path / "error.sqlite"
    HistoryStore(db).add(sample(cpu_percent=99))
    with TestClient(create_app(db, collect=False, interval=15), base_url="http://localhost") as client:
        client.app.state.collector_status.succeeded()
        client.app.state.collector_status.failed()
        result = client.get("/api/overview").json()
        assert result["collector"]["state"] == "error"
        assert result["collector"]["consecutive_failures"] == 1
        assert result["alerts"] == []
        assert client.get("/api/health").json()["status"] == "ok"
