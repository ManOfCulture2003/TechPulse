"""Exercise the actual PowerShell script against fake events, never host logs."""
import base64
import json
import shutil
import subprocess

import pytest

from app.windows_events import PS_SCRIPT


SHELL = shutil.which('powershell.exe') or shutil.which('pwsh')
pytestmark = pytest.mark.skipif(SHELL is None, reason='PowerShell is not installed')


def run_script(body):
    # The function shadows Get-WinEvent; no real Windows log is accessed.
    source = '''
function Get-WinEvent {
    [CmdletBinding()]
    param($FilterHashtable, $MaxEvents)
''' + body + '\n}\n' + PS_SCRIPT
    encoded = base64.b64encode(source.encode('utf-16le')).decode('ascii')
    return subprocess.run([SHELL, '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                          capture_output=True, text=True, timeout=20)


@pytest.mark.parametrize('error_id', ['UnauthorizedAccessException', 'NoMatchingLogsFound', 'UnexpectedProviderFailure'])
def test_log_read_errors_exit_unsuccessfully(error_id):
    result = run_script(f"Write-Error -Message 'simulated log failure' -ErrorId '{error_id}'")
    assert result.returncode != 0
    assert result.stdout.strip() != '[]'


def test_no_matching_events_is_a_successful_empty_result():
    result = run_script("Write-Error -Message 'simulated no matches' -ErrorId 'NoMatchingEventsFound'")
    assert result.returncode == 0
    assert json.loads(result.stdout) == []


def test_successful_query_returns_only_id_and_time():
    result = run_script("[pscustomobject]@{TimeCreated=[datetime]'2026-11-19T12:00:00Z'; UserName='not-for-output'}")
    assert result.returncode == 0
    events = json.loads(result.stdout)
    assert len(events) == 1
    assert set(events[0]) == {'id', 'time'}
    assert events[0]['id'] == 4625
    assert 'not-for-output' not in result.stdout
