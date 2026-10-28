from datetime import datetime, timedelta, timezone

from app.health_state import evaluate_sample_state


NOW = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)


def reading(seconds_ago: int) -> dict:
    return {"timestamp": (NOW - timedelta(seconds=seconds_ago)).isoformat(timespec="seconds")}


def test_waiting_when_no_samples():
    assert evaluate_sample_state(None, 15, now=NOW) == {
        "state": "waiting", "age_seconds": None, "stale_after_seconds": 45}


def test_freshness_boundary_and_stale_reading():
    assert evaluate_sample_state(reading(45), 15, now=NOW)["state"] == "fresh"
    assert evaluate_sample_state(reading(46), 15, now=NOW) == {
        "state": "stale", "age_seconds": 46, "stale_after_seconds": 45}


def test_longer_collection_interval_extends_freshness_window():
    assert evaluate_sample_state(reading(90), 60, now=NOW)["state"] == "fresh"
    assert evaluate_sample_state(reading(181), 60, now=NOW)["state"] == "stale"


def test_invalid_and_missing_timestamps_do_not_claim_healthy():
    for row in ({}, {"timestamp": "bad timestamp"}, {"timestamp": "2026-10-28T18:00:00"}, {"timestamp": None}):
        assert evaluate_sample_state(row, 15, now=NOW)["state"] == "invalid"


def test_future_timestamp_is_not_trusted():
    assert evaluate_sample_state(reading(-11), 15, now=NOW)["state"] == "invalid"
    assert evaluate_sample_state(reading(-10), 15, now=NOW)["age_seconds"] == 0


def test_zulu_timestamp_is_supported():
    assert evaluate_sample_state({"timestamp": "2026-10-28T17:59:45Z"}, 15, now=NOW)["state"] == "fresh"
