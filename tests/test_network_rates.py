"""Deterministic network-rate tests, independent of the host's real traffic."""
from types import SimpleNamespace

import pytest

from app.monitor import Monitor


def counters(sent, received):
    return SimpleNamespace(bytes_sent=sent, bytes_recv=received)


@pytest.fixture
def sampler(monkeypatch):
    monkeypatch.setattr("app.monitor.psutil.cpu_percent", lambda **kw: 10)
    monkeypatch.setattr("app.monitor.psutil.virtual_memory", lambda: SimpleNamespace(
        percent=25, used=2**30, total=4 * 2**30))
    monkeypatch.setattr("app.monitor.psutil.disk_usage", lambda path: SimpleNamespace(
        percent=50, free=10 * 2**30, total=20 * 2**30))
    monkeypatch.setattr("app.monitor.psutil.sensors_battery", lambda: None)
    monkeypatch.setattr("app.monitor.psutil.boot_time", lambda: 1700000000)

    def readings(network, ticks):
        network, ticks = iter(network), iter(ticks)
        monkeypatch.setattr("app.monitor.psutil.net_io_counters", lambda: next(network))
        monkeypatch.setattr("app.monitor.time.monotonic", lambda: next(ticks))
        return Monitor()
    return readings


def rates(sample):
    return sample["network_up_bps"], sample["network_down_bps"]


def test_first_sample_does_not_report_lifetime_totals(sampler):
    monitor = sampler([counters(500000, 900000), counters(500300, 900900)], [10, 13])
    assert rates(monitor.sample()) == (0, 0)
    assert rates(monitor.sample()) == (100, 300)


def test_primed_sample_uses_elapsed_time_and_independent_directions(sampler):
    monitor = sampler([counters(1000, 2000), counters(1600, 3500)], [10, 13])
    monitor.prime()
    assert rates(monitor.sample()) == (200, 500)


def test_counter_reset_is_clamped_and_next_interval_recovers(sampler):
    monitor = sampler([counters(1000, 2000), counters(100, 200), counters(500, 800)], [10, 12, 14])
    monitor.prime()
    assert rates(monitor.sample()) == (0, 0)
    assert rates(monitor.sample()) == (200, 300)


def test_missing_counters_require_new_baseline(sampler):
    monitor = sampler([counters(100, 200), None, counters(10000, 20000), counters(10600, 20900)],
                      [10, 13, 16, 19])
    monitor.prime()
    assert rates(monitor.sample()) == (0, 0)
    assert rates(monitor.sample()) == (0, 0)
    assert rates(monitor.sample()) == (200, 300)
