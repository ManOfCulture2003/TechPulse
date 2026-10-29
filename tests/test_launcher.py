"""Launcher tests use fakes: no browser, server, pip, or network is started."""
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess

import pytest

import launch


def test_environment_python_matches_platform(tmp_path):
    result = launch.environment_python(tmp_path)
    assert result.parent.name in {"Scripts", "bin"}
    assert result.name in {"python.exe", "python"}


def test_prepare_environment_reuses_healthy_unchanged_venv(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("fastapi>=0.115,<1\n")
    py = launch.environment_python(tmp_path)
    py.parent.mkdir(parents=True)
    py.touch()
    digest = hashlib.sha256((tmp_path / "requirements.txt").read_bytes()).hexdigest()
    (tmp_path / ".venv" / ".techpulse-requirements.sha256").write_text(digest + "\n")
    monkeypatch.setattr(launch, "dependencies_work", lambda _: True)
    with patch.object(launch.subprocess, "run") as run:
        assert launch.prepare_environment(tmp_path, "system-python") == py
        run.assert_not_called()


def test_prepare_environment_repairs_broken_dependencies(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("fastapi>=0.115,<1\n")
    py = launch.environment_python(tmp_path)
    py.parent.mkdir(parents=True)
    py.touch()
    digest = hashlib.sha256((tmp_path / "requirements.txt").read_bytes()).hexdigest()
    (tmp_path / ".venv" / ".techpulse-requirements.sha256").write_text(digest + "\n")
    calls = iter([False, True])
    monkeypatch.setattr(launch, "dependencies_work", lambda _: next(calls))
    with patch.object(launch.subprocess, "run") as run:
        assert launch.prepare_environment(tmp_path, "system-python") == py
        assert run.call_count == 1
        assert run.call_args.args[0][1:4] == ["-m", "pip", "install"]


def test_prepare_environment_reinstalls_when_requirements_change(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("fastapi>=0.115,<1\n")
    py = launch.environment_python(tmp_path)
    py.parent.mkdir(parents=True)
    py.touch()
    (tmp_path / ".venv" / ".techpulse-requirements.sha256").write_text("old\n")
    monkeypatch.setattr(launch, "dependencies_work", lambda _: True)
    with patch.object(launch.subprocess, "run") as run:
        launch.prepare_environment(tmp_path, "system-python")
        assert run.call_count == 1
    assert len((tmp_path / ".venv" / ".techpulse-requirements.sha256").read_text().strip()) == 64


def test_missing_requirements_explained(tmp_path):
    with pytest.raises(launch.LaunchError, match="requirements.txt is missing"):
        launch.prepare_environment(tmp_path, "python")


def test_failed_install_does_not_write_success_stamp(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("fastapi\n")
    py = launch.environment_python(tmp_path)
    py.parent.mkdir(parents=True)
    py.touch()
    with patch.object(launch.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip")):
        with pytest.raises(subprocess.CalledProcessError):
            launch.prepare_environment(tmp_path, "python")
    assert not (tmp_path / ".venv" / ".techpulse-requirements.sha256").exists()


def test_dependencies_work_detects_missing_packages():
    with patch.object(launch.subprocess, "run", return_value=Mock(returncode=1)):
        assert launch.dependencies_work(Path("python")) is False
    with patch.object(launch.subprocess, "run", side_effect=OSError("bad python")):
        assert launch.dependencies_work(Path("python")) is False


def test_server_ready_requires_valid_local_health_response():
    response = Mock(status=200)
    response.read.return_value = b'{"status":"ok","local_only":true}'
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    with patch.object(launch.urllib.request, "urlopen", return_value=response):
        assert launch.server_ready() is True
    response.read.return_value = b'{"status":"ok","local_only":false}'
    with patch.object(launch.urllib.request, "urlopen", return_value=response):
        assert launch.server_ready() is False
    with patch.object(launch.urllib.request, "urlopen", side_effect=OSError("offline")):
        assert launch.server_ready() is False


def test_server_opens_browser_only_after_health_ready(tmp_path):
    process = Mock()
    process.poll.side_effect = [None, None, None, 0]
    process.wait.return_value = 0
    with patch.object(launch.subprocess, "Popen", return_value=process), \
         patch.object(launch, "server_ready", side_effect=[False, True]), \
         patch.object(launch.time, "sleep") as sleep, \
         patch.object(launch.webbrowser, "open") as browser:
        assert launch.run_server(Path("python"), tmp_path) == 0
        sleep.assert_called_once()
        browser.assert_called_once_with(launch.DASHBOARD_URL)
        process.terminate.assert_not_called()


def test_server_exits_early_without_opening_browser(tmp_path):
    process = Mock()
    process.poll.return_value = 1
    with patch.object(launch.subprocess, "Popen", return_value=process), \
         patch.object(launch.webbrowser, "open") as browser:
        with pytest.raises(launch.LaunchError, match="exited before"):
            launch.run_server(Path("python"), tmp_path)
        browser.assert_not_called()


def test_server_timeout_cleans_up_child(tmp_path):
    process = Mock()
    process.poll.return_value = None
    process.wait.return_value = 0
    with patch.object(launch.subprocess, "Popen", return_value=process), \
         patch.object(launch, "server_ready", return_value=False), \
         patch.object(launch.time, "monotonic", side_effect=[0, 21]), \
         patch.object(launch.webbrowser, "open") as browser:
        with pytest.raises(launch.LaunchError, match="did not respond"):
            launch.run_server(Path("python"), tmp_path, timeout=20)
        process.terminate.assert_called_once()
        browser.assert_not_called()


def test_port_conflict_is_actionable():
    fake_socket = Mock()
    fake_socket.__enter__ = Mock(return_value=fake_socket)
    fake_socket.__exit__ = Mock(return_value=False)
    fake_socket.bind.side_effect = OSError("address in use")
    with patch.object(launch.socket, "socket", return_value=fake_socket):
        with pytest.raises(launch.LaunchError, match="already in use"):
            launch.check_port()


def test_main_returns_nonzero_when_startup_fails(monkeypatch):
    monkeypatch.setattr(launch, "check_port", lambda: (_ for _ in ()).throw(launch.LaunchError("busy")))
    assert launch.main() == 1
