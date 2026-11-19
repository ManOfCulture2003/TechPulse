"""Reject unsafe collector intervals before creating storage or background tasks."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.parametrize('interval', [0, -1, True, False, 0.1, 15.0, '15', None, float('nan'), float('inf'), 3601])
def test_invalid_interval_has_no_initialization_side_effects(tmp_path, interval):
    path = tmp_path / 'history' / 'metrics.sqlite'
    with patch('app.main.Monitor') as monitor:
        with pytest.raises(ValueError, match='interval'):
            create_app(path, interval=interval)
        monitor.assert_not_called()
    assert not path.parent.exists()


@pytest.mark.parametrize('interval', [1, 15, 3600])
def test_supported_interval_reaches_overview_and_diagnostics(tmp_path, interval):
    with TestClient(create_app(tmp_path / 'metrics.sqlite', collect=False, interval=interval),
                    base_url='http://localhost') as client:
        overview = client.get('/api/overview')
        assert overview.status_code == 200
        assert overview.json()['interval_seconds'] == interval
        assert client.get('/api/diagnostics.json').status_code == 200
