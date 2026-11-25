import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from app import windows_events as we


@pytest.mark.parametrize('stamp', [
    '0001-01-01T00:00:00+01:00',
    '9999-12-31T23:59:59-01:00',
])
def test_out_of_range_utc_conversion_does_not_hide_valid_events(stamp):
    good = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    response = Mock(returncode=0, stdout=json.dumps([
        {'id': 4625, 'time': stamp}, {'id': 4625, 'time': good},
    ]))
    with patch.object(we.platform, 'system', return_value='Windows'), patch.object(
        we.subprocess, 'run', return_value=response
    ):
        result = we.read_failed_logins()
    assert result['status'] == 'available'
    assert result['events'] == [{'id': 4625, 'time': good}]
