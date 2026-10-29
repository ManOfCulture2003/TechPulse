"""Beginner-friendly, local-only TechPulse launcher (standard library only).

This script runs under the system Python before project dependencies exist.
It prepares a virtual environment, waits for the actual local API to start,
and only then opens the dashboard in the user's browser.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765
HEALTH_URL = f"http://{HOST}:{PORT}/api/health"
DASHBOARD_URL = f"http://{HOST}:{PORT}"
MIN_PYTHON = (3, 11)
READY_TIMEOUT = 20


class LaunchError(RuntimeError):
    """A startup problem that can be explained without a Python traceback."""


def check_port() -> None:
    """Refuse to open an existing server or another app on the same port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((HOST, PORT))
    except OSError as exc:
        raise LaunchError(
            f"Port {PORT} is already in use. Close the existing app or stop "
            "the other program using that port, then try again."
        ) from exc


def environment_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def dependencies_work(python: Path) -> bool:
    """Detect missing packages even when an existing environment has a stamp."""
    try:
        result = subprocess.run(
            [str(python), "-c", "import fastapi, uvicorn, psutil"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10, check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def prepare_environment(root: Path, system_python: str) -> Path:
    """Install only on first run, changed requirements, or broken dependencies."""
    requirements = root / "requirements.txt"
    if not requirements.is_file():
        raise LaunchError("requirements.txt is missing. Re-download the full TechPulse folder.")
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    python = environment_python(root)
    if not python.is_file():
        print("[TechPulse] Creating a private Python environment...")
        subprocess.run([system_python, "-m", "venv", str(root / ".venv")], cwd=root, check=True)
    if not python.is_file():
        raise LaunchError("Python could not create .venv. Check your Python installation and folder permissions.")

    stamp = root / ".venv" / ".techpulse-requirements.sha256"
    current = stamp.read_text(encoding="utf-8").strip() if stamp.is_file() else None
    if current != digest or not dependencies_work(python):
        print("[TechPulse] Installing or repairing dependencies (internet may be needed)...")
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)], cwd=root, check=True)
        if not dependencies_work(python):
            raise LaunchError("Dependency installation finished, but required Python packages cannot be imported.")
        stamp.write_text(digest + "\n", encoding="utf-8")
    return python


def server_ready() -> bool:
    """Confirm the local API is actually responding, not merely that a port is open."""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=0.5) as response:
            if response.status != 200:
                return False
            data = json.loads(response.read(2048))
        return isinstance(data, dict) and data.get("status") == "ok" and data.get("local_only") is True
    except (OSError, ValueError, TypeError):
        return False


def run_server(python: Path, root: Path, timeout: float = READY_TIMEOUT) -> int:
    command = [str(python), "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(PORT)]
    process = subprocess.Popen(command, cwd=root)
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise LaunchError("The server exited before it became ready. Review the error above.")
            if server_ready():
                if process.poll() is not None:
                    raise LaunchError("The server stopped during startup. Review the error above.")
                print(f"[TechPulse] Dashboard ready: {DASHBOARD_URL}")
                print("[TechPulse] Keep this window open. Press Ctrl+C to stop.")
                try:
                    webbrowser.open(DASHBOARD_URL)
                except Exception:
                    print("[TechPulse] Browser could not open automatically. Use the URL above.")
                return process.wait()
            time.sleep(0.25)
        raise LaunchError("The server did not respond within 20 seconds. Review the error above.")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main() -> int:
    if sys.version_info < MIN_PYTHON:
        print("[TechPulse] Python 3.11 or newer is required. Install it from python.org.")
        return 2
    try:
        check_port()
        python = prepare_environment(ROOT, sys.executable)
        return run_server(python, ROOT)
    except (LaunchError, OSError, subprocess.CalledProcessError) as exc:
        print(f"[TechPulse] Startup failed: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\n[TechPulse] Monitoring stopped.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
