from unittest.mock import patch, Mock
from datetime import datetime, timedelta, timezone
import json
from app import windows_events as we


def test_unsupported_platform():
    with patch.object(we.platform, 'system', return_value='Linux'):
        result=we.read_failed_logins()
        assert result['status']=='unsupported'
        assert result['events']==[]


def test_windows_log_parsed_without_sensitive_names():
    stamp = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    fake=Mock(returncode=0,stdout=json.dumps([{"id":4625,"time":stamp,"secret":"dont-show"}]),stderr='')
    with patch.object(we.platform,'system',return_value='Windows'), patch.object(we.subprocess,'run',return_value=fake):
        result=we.read_failed_logins()
        assert result['status']=='available'
        assert result['events']==[{'id':4625,'time':stamp}]


def test_windows_log_permissions_are_handled():
    fake=Mock(returncode=5,stdout='',stderr='Access denied')
    with patch.object(we.platform,'system',return_value='Windows'), patch.object(we.subprocess,'run',return_value=fake):
        result=we.read_failed_logins()
        assert result['status']=='restricted'
        assert result['events']==[]


def test_invalid_ids_timestamps_and_private_fields_are_excluded():
    now = datetime.now(timezone.utc)
    good = (now - timedelta(minutes=2)).isoformat()
    old = (now - timedelta(days=2)).isoformat()
    future = (now + timedelta(hours=1)).isoformat()
    payload = [
        {"id": 4624, "time": good},
        {"id": True, "time": good},
        {"id": 4625, "time": "not-a-date"},
        {"id": 4625, "time": "2026-01-01T00:00:00"},
        {"id": 4625, "time": old},
        {"id": 4625, "time": future},
        {"id": 4625, "time": good, "username": "private"},
    ]
    fake = Mock(returncode=0, stdout=json.dumps(payload), stderr="")
    with patch.object(we.platform, "system", return_value="Windows"), patch.object(we.subprocess, "run", return_value=fake):
        result = we.read_failed_logins()
    assert result["status"] == "available"
    assert result["events"] == [{"id": 4625, "time": good}]
    assert "private" not in json.dumps(result)


def test_malformed_json_returns_unavailable_without_leaking_output():
    fake = Mock(returncode=0, stdout="{bad", stderr="secret")
    with patch.object(we.platform, "system", return_value="Windows"), patch.object(we.subprocess, "run", return_value=fake):
        result = we.read_failed_logins()
    assert result["status"] == "unavailable"
    assert result["events"] == []
    assert "secret" not in str(result)
