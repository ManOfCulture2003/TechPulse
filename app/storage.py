"""Small local SQLite history database. No telemetry leaves the machine."""
from __future__ import annotations

import csv
import io
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

COLUMNS = ("timestamp", "cpu_percent", "memory_percent", "disk_percent", "memory_used_gb",
           "memory_total_gb", "disk_free_gb", "disk_total_gb", "network_up_bps", "network_down_bps")


class HistoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.setup()

    @contextmanager
    def connection(self):
        """Commit or roll back each operation, then release its database handle."""
        conn = sqlite3.connect(self.path, timeout=5)
        try:
            conn.row_factory = sqlite3.Row
            # SQLite's own context manager handles transactions, not closing.
            with conn:
                yield conn
        finally:
            conn.close()

    def setup(self):
        with self.connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS samples (
                timestamp TEXT PRIMARY KEY, cpu_percent REAL NOT NULL,
                memory_percent REAL NOT NULL, disk_percent REAL NOT NULL,
                memory_used_gb REAL NOT NULL, memory_total_gb REAL NOT NULL,
                disk_free_gb REAL NOT NULL, disk_total_gb REAL NOT NULL,
                network_up_bps REAL NOT NULL, network_down_bps REAL NOT NULL
            )""")

    def add(self, sample: dict):
        vals = tuple(sample[key] for key in COLUMNS)
        placeholders = ",".join("?" for _ in COLUMNS)
        with self.connection() as conn:
            conn.execute(f"INSERT OR REPLACE INTO samples ({','.join(COLUMNS)}) VALUES ({placeholders})", vals)

    def recent(self, minutes: int = 120, limit: int = 240) -> list[dict]:
        since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM samples WHERE timestamp >= ? ORDER BY timestamp ASC", (since,)).fetchall()
        data = [dict(row) for row in rows]
        if len(data) <= limit:
            return data
        # Deterministic downsampling preserves the oldest and latest points.
        indices = [round(i * (len(data) - 1) / (limit - 1)) for i in range(limit)]
        return [data[i] for i in indices]

    def latest(self) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM samples ORDER BY timestamp DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def prune(self, keep_days: int = 7):
        since = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat(timespec="seconds")
        with self.connection() as conn:
            conn.execute("DELETE FROM samples WHERE timestamp < ?", (since,))

    def csv_export(self) -> str:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM samples ORDER BY timestamp ASC").fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow([row[col] for col in COLUMNS])
        return output.getvalue()

    def summary(self, minutes: int = 60, interval_seconds: int = 15, *, now: datetime | None = None) -> dict:
        """Summarize a bounded window using SQLite, without exporting raw readings.

        Gap counts are timestamp-based estimates, not proof of collector uptime.
        A gap is counted when adjacent samples are separated by at least two
        expected collection intervals (minimum 30 seconds).
        """
        if not 10 <= minutes <= 1440:
            raise ValueError("minutes must be between 10 and 1440")
        if not 1 <= interval_seconds <= 3600:
            raise ValueError("interval_seconds must be between 1 and 3600")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must have a time zone")
        current = current.astimezone(timezone.utc)
        start = (current - timedelta(minutes=minutes)).isoformat(timespec="seconds")
        end = current.isoformat(timespec="seconds")
        gap_threshold = max(30, 2 * interval_seconds)
        with self.connection() as conn:
            metrics = conn.execute("""
                SELECT COUNT(*) AS sample_count,
                       MIN(timestamp) AS first_sample_at,
                       MAX(timestamp) AS last_sample_at,
                       ROUND(AVG(cpu_percent), 1) AS avg_cpu_percent,
                       MAX(cpu_percent) AS max_cpu_percent,
                       ROUND(AVG(memory_percent), 1) AS avg_memory_percent,
                       MAX(memory_percent) AS max_memory_percent,
                       ROUND(AVG(disk_percent), 1) AS avg_disk_percent,
                       MAX(disk_percent) AS max_disk_percent
                FROM samples WHERE timestamp >= ? AND timestamp <= ?
            """, (start, end)).fetchone()
            gaps = conn.execute("""
                WITH ordered AS (
                    SELECT CAST(strftime('%s', timestamp) AS INTEGER) AS epoch,
                           LAG(CAST(strftime('%s', timestamp) AS INTEGER))
                               OVER (ORDER BY timestamp) AS previous_epoch
                    FROM samples WHERE timestamp >= ? AND timestamp <= ?
                )
                SELECT COUNT(*) AS large_gap_count,
                       MAX(epoch - previous_epoch) AS longest_gap_seconds
                FROM ordered
                WHERE previous_epoch IS NOT NULL
                  AND epoch - previous_epoch >= ?
            """, (start, end, gap_threshold)).fetchone()
        return {
            "window_minutes": minutes,
            "sample_count": metrics["sample_count"],
            "first_sample_at": metrics["first_sample_at"],
            "last_sample_at": metrics["last_sample_at"],
            "avg_cpu_percent": metrics["avg_cpu_percent"],
            "max_cpu_percent": metrics["max_cpu_percent"],
            "avg_memory_percent": metrics["avg_memory_percent"],
            "max_memory_percent": metrics["max_memory_percent"],
            "avg_disk_percent": metrics["avg_disk_percent"],
            "max_disk_percent": metrics["max_disk_percent"],
            "large_gap_count": gaps["large_gap_count"],
            "longest_gap_seconds": gaps["longest_gap_seconds"] or 0,
            "gap_threshold_seconds": gap_threshold,
        }
