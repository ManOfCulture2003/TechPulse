from unittest.mock import patch
from datetime import datetime, timezone
import pytest
from app.storage import HistoryStore, COLUMNS


def row(stamp, value=1):
    return {**dict.fromkeys(COLUMNS, value), 'timestamp': stamp}


def test_offsets_are_normalized_without_mutating_input(tmp_path):
    store = HistoryStore(tmp_path / 'data.db')
    original = row('2026-11-26T15:00:00-05:00')
    store.add(original)
    store.add(row('2026-11-26T19:59:00+00:00', 2))
    assert store.latest()['timestamp'] == '2026-11-26T20:00:00+00:00'
    assert original['timestamp'].endswith('-05:00')
    with patch('app.storage.datetime') as clock:
        clock.now.return_value = datetime(2026, 11, 26, 20, 1, tzinfo=timezone.utc)
        assert len(store.recent(minutes=10)) == 2
    store.add(row('2026-11-26T20:00:00Z', 3))
    assert store.latest()['cpu_percent'] == 3
    with store.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM samples').fetchone()[0] == 2


@pytest.mark.parametrize('stamp', [None, 123, 'bad', '2026-11-26T20:00:00', '0001-01-01T00:00:00+01:00'])
def test_invalid_timestamps_do_not_write(tmp_path, stamp):
    store = HistoryStore(tmp_path / 'data.db')
    with pytest.raises(ValueError, match='timestamp'):
        store.add(row(stamp))
    assert store.latest() is None
