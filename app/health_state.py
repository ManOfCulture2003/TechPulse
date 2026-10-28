"""Decide whether persisted metrics are safe to present as current readings."""
from __future__ import annotations

from datetime import datetime, timezone


def evaluate_sample_state(sample: dict | None, interval_seconds: int, *, now: datetime | None = None) -> dict:
    """Return an explicit freshness status for the latest recorded sample.

    A prior run can leave a healthy-looking row in SQLite even after collection
    stops. These states distinguish current evidence from historical readings.
    """
    threshold = max(45, interval_seconds * 3)
    result = {"state": "waiting", "age_seconds": None, "stale_after_seconds": threshold}
    if sample is None:
        return result

    try:
        value = sample["timestamp"]
        if not isinstance(value, str):
            raise ValueError("timestamp must be a string")
        recorded_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if recorded_at.tzinfo is None:
            raise ValueError("timestamp requires a time zone")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("current time requires a time zone")
        age = (current.astimezone(timezone.utc) - recorded_at.astimezone(timezone.utc)).total_seconds()
    except (KeyError, TypeError, ValueError, OverflowError):
        return {**result, "state": "invalid"}

    # A clock moving ahead by more than ten seconds cannot provide trusted age.
    if age < -10:
        return {**result, "state": "invalid"}
    return {**result, "state": "stale" if age > threshold else "fresh", "age_seconds": max(0, round(age))}
