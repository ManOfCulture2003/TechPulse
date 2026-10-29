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
