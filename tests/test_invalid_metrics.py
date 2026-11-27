from datetime import datetime, timezone
import json

import pytest
from app.storage import COLUMNS, HistoryStore


@pytest.mark.parametrize('field,value', [
    ('cpu_percent', float('inf')), ('memory_percent', float('nan')),
    ('disk_percent', 101), ('network_up_bps', -1),
    ('network_down_bps', True), ('memory_used_gb', '8'),
    ('disk_free_gb', None), ('memory_total_gb', -2),
])
def test_bad_reading_cannot_replace_valid_history(tmp_path, field, value):
    store = HistoryStore(tmp_path / 'metrics.db')
    good = dict.fromkeys(COLUMNS, 1)
    good['timestamp'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    store.add(good)
    bad = {**good, field: value}
    with pytest.raises(ValueError, match=field):
        store.add(bad)
    assert store.latest() == good
    json.dumps(store.latest(), allow_nan=False)


def test_zero_and_full_percentages_are_valid(tmp_path):
    store = HistoryStore(tmp_path / 'metrics.db')
    sample = dict.fromkeys(COLUMNS, 0)
    sample.update(timestamp=datetime.now(timezone.utc).isoformat(timespec='seconds'), cpu_percent=100)
    store.add(sample)
    assert store.latest() == sample
