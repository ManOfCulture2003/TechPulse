from datetime import datetime, timedelta, timezone
import sqlite3
from unittest.mock import patch

import pytest
from app.storage import HistoryStore


def datum(i=0, timestamp=None):
    return {"timestamp": timestamp or (datetime.now(timezone.utc)+timedelta(seconds=i-60)).isoformat(timespec='seconds'),
        "cpu_percent": i%100,"memory_percent": 40,"disk_percent": 30,
        "memory_used_gb": 8,"memory_total_gb": 16,
        "disk_free_gb": 160,"disk_total_gb": 200,
        "network_up_bps": i,"network_down_bps": i*2}


def test_downsample_preserves_endpoints(tmp_path):
    db=HistoryStore(tmp_path/'data.db')
    for i in range(21): db.add(datum(i))
    points=db.recent(minutes=10,limit=5)
    assert len(points)==5
    assert points[0]['cpu_percent']==0
    assert points[-1]['cpu_percent']==20


def test_recent_excludes_future_and_old_samples(tmp_path):
    now = datetime(2026, 11, 5, 20, tzinfo=timezone.utc)
    db = HistoryStore(tmp_path / 'window.db')
    for value, offset in enumerate((-601, -600, -1, 0, 1, 600)):
        db.add(datum(value, timestamp=(now + timedelta(seconds=offset)).isoformat(timespec='seconds')))
    with patch('app.storage.datetime') as clock:
        clock.now.return_value = now
        points = db.recent(minutes=10)
        downsampled = db.recent(minutes=10, limit=2)
    assert [p['cpu_percent'] for p in points] == [1, 2, 3]
    assert [p['cpu_percent'] for p in downsampled] == [1, 3]


def test_prune_old_history(tmp_path):
    db=HistoryStore(tmp_path/'data.db')
    db.add(datum(1))
    older=(datetime.now(timezone.utc)-timedelta(days=10)).isoformat(timespec='seconds')
    db.add(datum(99,timestamp=older))
    db.prune(7)
    assert db.latest()['cpu_percent']==1
    assert len(db.csv_export().splitlines())==2


def test_insert_replacement_is_idempotent(tmp_path):
    db=HistoryStore(tmp_path/'data.db')
    one=datum(5)
    db.add(one);db.add(one)
    assert len(db.recent())==1


def test_connection_commits_and_closes(tmp_path):
    db = HistoryStore(tmp_path / 'data.db')
    with db.connection() as conn:
        conn.execute("CREATE TABLE marker (value INTEGER)")
        conn.execute("INSERT INTO marker VALUES (7)")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    with db.connection() as reopened:
        assert reopened.execute("SELECT value FROM marker").fetchone()[0] == 7


def test_connection_rolls_back_and_closes_on_error(tmp_path):
    db = HistoryStore(tmp_path / 'data.db')
    with db.connection() as setup:
        setup.execute("CREATE TABLE marker (value INTEGER)")

    with pytest.raises(RuntimeError, match="interrupted write"):
        with db.connection() as conn:
            conn.execute("INSERT INTO marker VALUES (7)")
            raise RuntimeError("interrupted write")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    with db.connection() as reopened:
        assert reopened.execute("SELECT COUNT(*) FROM marker").fetchone()[0] == 0


def test_csv_stream_filters_window_and_future_and_has_header(tmp_path):
    import csv
    import io
    db = HistoryStore(tmp_path / "csv.db")
    now = datetime(2026, 11, 17, 20, tzinfo=timezone.utc)
    for value, offset in [(1, -601), (2, -600), (3, -5), (4, 5)]:
        db.add(datum(value, timestamp=(now + timedelta(seconds=offset)).isoformat(timespec="seconds")))
    result = "".join(db.csv_stream(minutes=10, now=now))
    records = list(csv.DictReader(io.StringIO(result)))
    assert [float(row["cpu_percent"]) for row in records] == [2, 3]


def test_csv_stream_rejects_oversized_before_any_output(tmp_path):
    db = HistoryStore(tmp_path / "csv.db")
    now = datetime(2026, 11, 17, 20, tzinfo=timezone.utc)
    for i in range(3):
        db.add(datum(i, timestamp=(now - timedelta(seconds=i)).isoformat(timespec="seconds")))
    with pytest.raises(ValueError, match="row safety limit"):
        db.csv_stream(minutes=10, now=now, max_rows=2)
    assert len(list(db.csv_stream(minutes=10, now=now, max_rows=3))) == 4


def test_csv_stream_rejects_invalid_inputs(tmp_path):
    db = HistoryStore(tmp_path / "csv.db")
    for minutes in (0, 9, 10081, True):
        with pytest.raises(ValueError, match="minutes"):
            db.csv_stream(minutes=minutes)
    with pytest.raises(ValueError, match="time zone"):
        db.csv_stream(now=datetime(2026, 11, 17))
    with pytest.raises(ValueError, match="max_rows"):
        db.csv_stream(max_rows=0)
