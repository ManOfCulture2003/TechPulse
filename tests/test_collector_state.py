"""Collector lifecycle tests without reading actual device data."""
from app.collector_state import CollectorStatus


def test_disabled_and_starting_are_distinct():
    assert CollectorStatus(enabled=False).snapshot()["state"] == "disabled"
    assert CollectorStatus().snapshot()["state"] == "starting"


def test_failure_recovery_and_counter_reset():
    status = CollectorStatus()
    status.failed()
    status.failed()
    failed = status.snapshot()
    assert failed["state"] == "error"
    assert failed["consecutive_failures"] == 2
    assert failed["last_failure_at"]
    assert failed["last_success_at"] is None
    status.succeeded()
    recovered = status.snapshot()
    assert recovered["state"] == "running"
    assert recovered["consecutive_failures"] == 0
    assert recovered["samples_collected"] == 1
    assert recovered["last_success_at"]


def test_stopped_does_not_turn_disabled_into_stopped():
    disabled = CollectorStatus(enabled=False)
    disabled.stopped()
    assert disabled.snapshot()["state"] == "disabled"
    active = CollectorStatus()
    active.succeeded()
    active.stopped()
    assert active.snapshot()["state"] == "stopped"


def test_snapshot_is_not_mutable_internal_state():
    status = CollectorStatus()
    copy = status.snapshot()
    copy["state"] = "running"
    copy["samples_collected"] = 99
    assert status.snapshot()["state"] == "starting"
    assert status.snapshot()["samples_collected"] == 0
