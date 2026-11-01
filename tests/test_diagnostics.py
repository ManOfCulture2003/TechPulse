"""Regression tests for privacy-minimized local diagnostic exports."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage import HistoryStore


NOW = datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc)


def row(seconds_ago: int, cpu: float = 20) -> dict:
    return {
        "timestamp": (NOW - timedelta(seconds=seconds_ago)).isoformat(timespec="seconds"),
        "cpu_percent": cpu, "memory_percent": 40.0, "disk_percent": 60.0,
        "memory_used_gb": 8.0, "memory_total_gb": 16.0,
        "disk_free_gb": 100.0, "disk_total_gb": 250.0,
        "network_up_bps": 0, "network_down_bps": 0,
    }


def test_summary_uses_sql_aggregates_and_counts_large_gaps(tmp_path):
    store = HistoryStore(tmp_path / "data.sqlite")
    for age, cpu in [(50, 20), (40, 40), (5, 60)]:
        store.add(row(age, cpu))
    store.add(row(3700, 99))  # outside the selected 60-minute window
    store.add(row(-30, 99))  # future clock reading must not affect the report
    report = store.summary(minutes=60, interval_seconds=15, now=NOW)
    assert report["sample_count"] == 3
    assert report["avg_cpu_percent"] == 40.0
    assert report["max_cpu_percent"] == 60
    assert report["large_gap_count"] == 1
    assert report["longest_gap_seconds"] == 35
    assert report["gap_threshold_seconds"] == 30
    assert report["first_sample_at"] == row(50)["timestamp"]
    assert report["last_sample_at"] == row(5)["timestamp"]


def test_summary_handles_empty_window_and_invalid_arguments(tmp_path):
    store = HistoryStore(tmp_path / "empty.sqlite")
    result = store.summary(now=NOW)
    assert result["sample_count"] == 0
    assert result["avg_cpu_percent"] is None
    assert result["large_gap_count"] == 0
    assert result["longest_gap_seconds"] == 0
    with pytest.raises(ValueError):
        store.summary(minutes=0, now=NOW)
    with pytest.raises(ValueError):
        store.summary(interval_seconds=0, now=NOW)
    with pytest.raises(ValueError):
        store.summary(now=NOW.replace(tzinfo=None))


def test_diagnostics_download_has_safe_shape_and_no_raw_device_data(tmp_path):
    db = tmp_path / "private-folder" / "system.sqlite"
    HistoryStore(db).add({
        **row(5),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    with TestClient(create_app(db, collect=False), base_url="http://localhost") as client:
        response = client.get("/api/diagnostics.json?minutes=60")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment;" in response.headers["content-disposition"]
        assert response.headers["cache-control"] == "no-store"
        report = response.json()
        assert report["schema_version"] == 1
        assert report["history"]["sample_count"] == 1
        assert report["collector"]["state"] == "disabled"
        assert report["latest_reading"]["live_metrics_available"] is False
        assert set(report) == {
            "schema_version", "report_type", "generated_at", "collector",
            "latest_reading", "history", "privacy_note", "limitations",
        }
        assert "private-folder" not in response.text
        assert "system.sqlite" not in response.text
        assert "processes" not in report
        assert "events" not in report


def test_diagnostics_reports_live_state_only_after_collector_success(tmp_path):
    db = tmp_path / "app.sqlite"
    sample = row(5)
    sample["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    HistoryStore(db).add(sample)
    with TestClient(create_app(db, collect=False), base_url="http://localhost") as client:
        assert client.get("/api/diagnostics.json").json()["latest_reading"]["live_metrics_available"] is False
        client.app.state.collector_status.succeeded()
        report = client.get("/api/diagnostics.json").json()
        assert report["latest_reading"]["state"] == "fresh"
        assert report["latest_reading"]["live_metrics_available"] is True


def test_diagnostics_validates_window_and_rejects_untrusted_host(tmp_path):
    with TestClient(create_app(tmp_path / "db.sqlite", collect=False), base_url="http://localhost") as client:
        assert client.get("/api/diagnostics.json?minutes=9").status_code == 422
        assert client.get("/api/diagnostics.json?minutes=1441").status_code == 422
        assert client.get("/api/diagnostics.json", headers={"host": "evil.example"}).status_code == 400
