from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from app.storage import COLUMNS, HistoryStore


def test_single_point_returns_latest_in_window(tmp_path):
    db = HistoryStore(tmp_path / 'history.db')
    assert db.recent(limit=1) == []
    now = datetime.now(timezone.utc).replace(microsecond=0)
    for seconds in (-120, -60, 60):
        row = dict.fromkeys(COLUMNS, 1)
        row['timestamp'] = (now + timedelta(seconds=seconds)).isoformat()
        db.add(row)
    assert db.recent(limit=1)[0]['timestamp'] == (now - timedelta(seconds=60)).isoformat()


@pytest.mark.parametrize('limit', [0, -1, True, 1.5, '2', None])
def test_invalid_limit_rejected_even_when_history_empty(tmp_path, limit):
    db = HistoryStore(tmp_path / 'history.db')
    with patch.object(db, 'connection') as connection:
        with pytest.raises(ValueError, match='limit'):
            db.recent(limit=limit)
        connection.assert_not_called()
