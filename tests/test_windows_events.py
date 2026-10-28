from unittest.mock import patch, Mock
from app import windows_events as we


def test_unsupported_platform():
    with patch.object(we.platform, 'system', return_value='Linux'):
        result=we.read_failed_logins()
        assert result['status']=='unsupported'
        assert result['events']==[]


def test_windows_log_parsed_without_sensitive_names():
    fake=Mock(returncode=0,stdout='[{"id":4625,"time":"2026-10-28T12:00:00Z","secret":"dont-show"}]',stderr='')
    with patch.object(we.platform,'system',return_value='Windows'), patch.object(we.subprocess,'run',return_value=fake):
        result=we.read_failed_logins()
        assert result['status']=='available'
        assert result['events']==[{'id':4625,'time':'2026-10-28T12:00:00Z'}]


def test_windows_log_permissions_are_handled():
    fake=Mock(returncode=5,stdout='',stderr='Access denied')
    with patch.object(we.platform,'system',return_value='Windows'), patch.object(we.subprocess,'run',return_value=fake):
        result=we.read_failed_logins()
        assert result['status']=='restricted'
        assert result['events']==[]
