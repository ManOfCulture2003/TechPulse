"""Thread-safe, non-sensitive status for the local metrics collector."""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CollectorStatus:
    """Distinguish API availability from successful metrics collection.

    A live HTTP server is not proof that its background sampler is working.
    No exception messages, usernames, paths, or process details are exposed.
    """

    def __init__(self, enabled: bool = True):
        self._lock = Lock()
        self._state = "starting" if enabled else "disabled"
        self._last_success_at: str | None = None
        self._last_failure_at: str | None = None
        self._consecutive_failures = 0
        self._samples_collected = 0

    def succeeded(self) -> None:
        with self._lock:
            self._state = "running"
            self._last_success_at = utc_timestamp()
            self._consecutive_failures = 0
            self._samples_collected += 1

    def failed(self) -> None:
        with self._lock:
            self._state = "error"
            self._last_failure_at = utc_timestamp()
            self._consecutive_failures += 1

    def stopped(self) -> None:
        with self._lock:
            if self._state != "disabled":
                self._state = "stopped"

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "last_success_at": self._last_success_at,
                "last_failure_at": self._last_failure_at,
                "consecutive_failures": self._consecutive_failures,
                "samples_collected": self._samples_collected,
            }
