from datetime import datetime, timedelta, timezone
import sqlite3

import pytest
from app.storage import HistoryStore


def datum(i=0, timestamp=None):
    return {"timestamp": timestamp or (datetime.now(timezone.utc)+timedelta(seconds=i)).isoformat(timespec='seconds'),
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
