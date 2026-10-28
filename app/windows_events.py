"""Optional read-only Windows Security log summary; no usernames or IPs returned."""
from __future__ import annotations
import json
import platform
import subprocess

# Static PowerShell, no input interpolation. Only event ID and timestamp are returned.
PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$events = @(Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625; StartTime=(Get-Date).AddHours(-24)} -MaxEvents 25 -ErrorAction SilentlyContinue)
$items = @($events | ForEach-Object { @{ id = 4625; time = $_.TimeCreated.ToUniversalTime().ToString('o') } })
ConvertTo-Json -InputObject $items -Compress -Depth 3
"""


def read_failed_logins() -> dict:
    if platform.system() != "Windows":
        return {"status": "unsupported", "message": "Windows Security log is only available on Windows.", "events": []}
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", PS_SCRIPT],
            capture_output=True, text=True, timeout=12, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unavailable", "message": "Windows Event Log could not be read.", "events": []}
    if result.returncode != 0:
        return {"status": "restricted", "message": "Windows Security log access is unavailable or restricted. Basic monitoring still works.", "events": []}
    try:
        raw = json.loads(result.stdout)
        if not isinstance(raw, list):
            return {"status": "unavailable", "message": "Unexpected Event Log response.", "events": []}
        events = [{"id": 4625, "time": str(event["time"])} for event in raw[:25] if isinstance(event, dict) and "time" in event]
        return {"status": "available", "message": "Failed Windows sign-ins (event 4625) from the last 24 hours. Not proof of an attack.", "events": events}
    except (ValueError, KeyError, TypeError):
        return {"status": "unavailable", "message": "Could not parse the Event Log response.", "events": []}
