import pytest

from app.engine.engine import SignalEngine
from app.engine.events import SignalAction
from app.engine.feed import HistoricalBarFeed
from app.strategies.mean_reversion import MeanReversion
from tests.factories import series

RISE = list(range(100, 120))          # 20 steady up days: 100..119
DIP = [118, 117, 116, 115]            # four down days; RSI(2) goes 50, 25, 12.5, 6.25


def run(closes, **kwargs):
    params = dict(entry_threshold=10, trend_window=20, exit_window=5, max_hold_days=3)
    params.update(kwargs)
    return SignalEngine([MeanReversion(**params)]).run(HistoricalBarFeed({"TEST": series(closes)})).signals


def test_buys_the_fourth_down_day_in_an_uptrend():
    signals = run(RISE + DIP)
    assert [(s.action, int(s.price)) for s in signals] == [(SignalAction.BUY, 115)]


def test_no_entry_when_below_the_trend_average():
    falling = list(range(140, 120, -1))
    assert run(falling + [119, 118, 117, 116]) == []


def test_exits_when_close_rises_above_short_average():
    signals = run(RISE + DIP + [116, 118])
    assert [s.action for s in signals] == [SignalAction.BUY, SignalAction.SELL]
    assert "average" in signals[-1].reason


def test_exits_on_the_time_limit_when_no_bounce_comes():
    signals = run(RISE + DIP + [114, 113, 112])
    assert [s.action for s in signals] == [SignalAction.BUY, SignalAction.SELL]
    assert "time limit" in signals[-1].reason
    assert signals[-1].ts.day - signals[0].ts.day == 3


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        MeanReversion(entry_threshold=0)
