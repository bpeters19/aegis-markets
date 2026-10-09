from datetime import datetime, timezone

import pytest

from app.backtest import holdout
from app.backtest.holdout import HoldoutLockedError, check_period


def at(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


def test_period_ending_on_lock_date_is_allowed():
    check_period(at(2023, 1, 1))


def test_period_past_lock_date_is_refused():
    with pytest.raises(HoldoutLockedError):
        check_period(at(2024, 1, 1))


def test_unlock_requires_a_reason():
    with pytest.raises(HoldoutLockedError):
        check_period(at(2024, 1, 1), unlock=True, reason="  ")


def test_unlock_with_reason_is_logged(tmp_path, monkeypatch):
    log = tmp_path / "holdout-log.md"
    monkeypatch.setattr(holdout, "LOG_PATH", log)
    check_period(at(2024, 1, 1), unlock=True, reason="final test of H1", command="holdout")
    assert "final test of H1" in log.read_text()
    assert "| holdout |" in log.read_text()
