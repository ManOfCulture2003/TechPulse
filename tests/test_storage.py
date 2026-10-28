from datetime import datetime, timedelta, timezone
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
