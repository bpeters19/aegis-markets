import math

import pytest

from app.risk.volatility import VolatilityTracker
from tests.factories import make_bar


def test_no_estimate_until_enough_history():
    tracker = VolatilityTracker(lookback=2)
    tracker.update(make_bar(100, day=0))
    tracker.update(make_bar(110, day=1))
    assert tracker.annualized("TEST") is None


def test_annualized_sample_volatility():
    tracker = VolatilityTracker(lookback=2)
    for day, close in enumerate([100, 110, 99]):
        tracker.update(make_bar(close, day=day))
    # returns +10% and -10%: sample stdev 0.1414, annualized x sqrt(252)
    assert tracker.annualized("TEST") == pytest.approx(0.141421356 * math.sqrt(252))


def test_symbols_are_tracked_separately():
    tracker = VolatilityTracker(lookback=2)
    for day, close in enumerate([100, 110, 99]):
        tracker.update(make_bar(close, day=day))
    tracker.update(make_bar(50, day=0, symbol="OTHER"))
    assert tracker.annualized("OTHER") is None
