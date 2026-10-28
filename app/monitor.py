"""Collect local, read-only machine metrics with psutil."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import time

import psutil


@dataclass
class Monitor:
    """Stateful sampler used by a single background task.

    Network rates need two counter readings. The initial sample reports zero,
    rather than pretending total bytes since boot are bytes per second.
    """

    previous_network: object | None = None
    previous_tick: float | None = None

    def prime(self) -> None:
        psutil.cpu_percent(interval=None)
        self.previous_network = psutil.net_io_counters()
        self.previous_tick = time.monotonic()

    def sample(self) -> dict:
        cpu = round(psutil.cpu_percent(interval=None), 1)
        memory = psutil.virtual_memory()
        anchor = Path.home().anchor if os.name == "nt" else "/"
        try:
            disk = psutil.disk_usage(anchor)
        except OSError:
            disk = psutil.disk_usage("/")

        net = psutil.net_io_counters()
        now = time.monotonic()
        if net is not None and self.previous_network is not None and self.previous_tick is not None:
            elapsed = max(now - self.previous_tick, .001)
            sent_rate = max(0.0, (net.bytes_sent - self.previous_network.bytes_sent) / elapsed)
            received_rate = max(0.0, (net.bytes_recv - self.previous_network.bytes_recv) / elapsed)
        else:
            sent_rate = received_rate = 0.0
        self.previous_network, self.previous_tick = net, now

        battery = None
        try:
            b = psutil.sensors_battery()
            if b is not None:
                battery = {"percent": round(b.percent, 1), "plugged": bool(b.power_plugged)}
        except (AttributeError, OSError):
            pass

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cpu_percent": cpu,
            "memory_percent": round(memory.percent, 1),
            "disk_percent": round(disk.percent, 1),
            "memory_used_gb": round(memory.used / (1024 ** 3), 2),
            "memory_total_gb": round(memory.total / (1024 ** 3), 2),
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "network_up_bps": round(sent_rate),
            "network_down_bps": round(received_rate),
            "boot_time": datetime.fromtimestamp(psutil.boot_time(), timezone.utc).isoformat(timespec="seconds"),
            "battery": battery,
            "os_name": f"{platform.system()} {platform.release()}",
        }


def top_processes(limit: int = 7) -> list[dict]:
    """Read-only snapshot ranked by resident memory; no termination operations."""
    entries = []
    for process in psutil.process_iter(attrs=["pid", "name", "memory_info"]):
        try:
            info = process.info
            mem = info["memory_info"]
            if mem is None:
                continue
            entries.append({"pid": int(info["pid"]),
                            "name": str(info["name"] or "Unknown")[:90],
                            "memory_mb": round(mem.rss / (1024 ** 2), 1)})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            continue
    return sorted(entries, key=lambda row: row["memory_mb"], reverse=True)[:limit]


def compute_alerts(sample: dict) -> list[dict]:
    """Explainable thresholds; not a virus detector or security risk score."""
    rules = [
        ("cpu_percent", 90, "High CPU load", "Close unused apps or check Task Manager for demanding processes."),
        ("memory_percent", 85, "Memory pressure", "Review high-memory apps and close programs you no longer need."),
        ("disk_percent", 90, "Storage running low", "Free space on your system drive and review large unused files."),
    ]
    alerts = []
    for key, threshold, title, advice in rules:
        value = sample.get(key)
        if value is not None and value >= threshold:
            alerts.append({"code": key, "level": "warning", "title": title,
                           "detail": f"{value:.1f}% used (threshold: {threshold}%).", "advice": advice})
    return alerts
