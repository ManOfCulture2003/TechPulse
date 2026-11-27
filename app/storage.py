"""Small local SQLite history database. No telemetry leaves the machine."""
from __future__ import annotations

import csv
import io
import math
from numbers import Real
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
        # SQLite compares these timestamps as text; offsets must share one format.
        try:
            stamp = datetime.fromisoformat(sample["timestamp"].replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("timestamp requires a time zone")
            normalized = stamp.astimezone(timezone.utc).isoformat(timespec="seconds")
        except (KeyError, AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("timestamp must be a valid time-zone-aware date") from exc
        sample = {**sample, "timestamp": normalized}
        for key in COLUMNS[1:]:
            value = sample.get(key)
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"{key} must be a finite nonnegative number")
            try:
                value = float(value)
                valid = math.isfinite(value) and value >= 0
            except OverflowError:
                valid = False
            if not valid or (key.endswith("_percent") and value > 100):
                raise ValueError(f"{key} is outside its valid measurement range")
            sample[key] = value
        vals = tuple(sample[key] for key in COLUMNS)
        placeholders = ",".join("?" for _ in COLUMNS)
        with self.connection() as conn:
            conn.execute(f"INSERT OR REPLACE INTO samples ({','.join(COLUMNS)}) VALUES ({placeholders})", vals)

    def recent(self, minutes: int = 120, limit: int = 240) -> list[dict]:
        current = datetime.now(timezone.utc)
        since = (current - timedelta(minutes=minutes)).isoformat(timespec="seconds")
        until = current.isoformat(timespec="seconds")
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM samples WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC",
                (since, until),
            ).fetchall()
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


    def csv_stream(self, minutes: int = 10080, *, now: datetime | None = None, max_rows: int = 10000):
        """Yield CSV rows incrementally. Reject exports exceeding the configured row cap.

        The preflight count avoids starting an HTTP response that cannot finish.
        LIMIT protects against concurrent inserts between the count and streaming.
        """
        if not isinstance(minutes, int) or isinstance(minutes, bool) or not 10 <= minutes <= 10080:
            raise ValueError("minutes must be between 10 and 10080")
        if not isinstance(max_rows, int) or isinstance(max_rows, bool) or not 1 <= max_rows <= 100000:
            raise ValueError("max_rows must be between 1 and 100000")
        current = now if now is not None else datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("now must have a time zone")
        current = current.astimezone(timezone.utc)
        start = (current - timedelta(minutes=minutes)).isoformat(timespec="seconds")
        end = current.isoformat(timespec="seconds")
        sql_where = "timestamp >= ? AND timestamp <= ?"
        with self.connection() as conn:
            # Stop counting at the first record beyond the cap.
            count = conn.execute(
                f"SELECT COUNT(*) FROM (SELECT 1 FROM samples WHERE {sql_where} LIMIT ?)",
                (start, end, max_rows + 1),
            ).fetchone()[0]
        if count > max_rows:
            raise ValueError("CSV export exceeds the 10000-row safety limit; choose a shorter time window")

        def rows():
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(COLUMNS)
            yield buffer.getvalue()
            with self.connection() as conn:
                cursor = conn.execute(
                    f"SELECT {','.join(COLUMNS)} FROM samples WHERE {sql_where} "
                    "ORDER BY timestamp ASC LIMIT ?",
                    (start, end, max_rows),
                )
                for record in cursor:
                    buffer.seek(0)
                    buffer.truncate(0)
                    writer.writerow([record[column] for column in COLUMNS])
                    yield buffer.getvalue()
        return rows()

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
