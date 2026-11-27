from datetime import datetime, timezone, timedelta
import json
from fastapi.testclient import TestClient
from app.main import create_app
from app.storage import COLUMNS, HistoryStore
import pytest


def test_normalized_valid_sample_survives_bad_replacement_across_endpoints(tmp_path):
    path = tmp_path / 'data.db'
    store = HistoryStore(path)
    stamp = (datetime.now(timezone(timedelta(hours=-5))) - timedelta(seconds=2)).isoformat(timespec='seconds')
    good = {**dict.fromkeys(COLUMNS, 1), 'timestamp': stamp}
    store.add(good)
    with pytest.raises(ValueError):
        store.add({**good, 'cpu_percent': float('inf')})
    with TestClient(create_app(path, collect=False), base_url='http://127.0.0.1') as client:
        for endpoint in ['/api/overview', '/api/history', '/api/diagnostics.json']:
            response = client.get(endpoint)
            assert response.status_code == 200
            json.dumps(response.json(), allow_nan=False)
        assert len(client.get('/api/history').json()['points']) == 1
        assert client.get('/api/export.csv').status_code == 200
    assert store.latest()['timestamp'].endswith('+00:00')
    assert good['timestamp'] == stamp


def test_large_finite_integer_uses_real_binding_without_mutating_input(tmp_path):
    store = HistoryStore(tmp_path / 'data.db')
    sample = {**dict.fromkeys(COLUMNS, 1),
              'timestamp': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'network_up_bps': 2**70}
    store.add(sample)
    assert store.latest()['network_up_bps'] == float(2**70)
    assert isinstance(sample['network_up_bps'], int)
