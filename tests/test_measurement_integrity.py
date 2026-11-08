from unittest.mock import patch
import pytest
from app.monitor import Monitor
from app.storage import HistoryStore
from test_app import sample


@pytest.mark.parametrize('value', [None, float('nan'), float('inf'), -1, True, '30', 101])
def test_invalid_cpu_never_becomes_a_saved_healthy_reading(tmp_path, value):
    store=HistoryStore(tmp_path/'metrics.sqlite')
    with pytest.raises(ValueError):
        store.add(sample(cpu_percent=value))
    assert store.latest() is None


def test_cpu_is_measured_on_current_worker_thread():
    with patch('app.monitor.psutil.cpu_percent', return_value=25) as cpu:
        Monitor().sample()
        cpu.assert_called_once_with(interval=0.2)
