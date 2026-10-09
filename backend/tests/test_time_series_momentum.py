from datetime import date
from decimal import Decimal

import pytest

from app.engine.engine import SignalEngine
from app.engine.events import SignalAction
from app.engine.feed import HistoricalBarFeed
from app.strategies.time_series_momentum import TimeSeriesMomentum
from tests.factories import series

MONTH_STARTS = [date(2026, 2, 1), date(2026, 3, 1)]


def run(closes, lookback=3):
    engine = SignalEngine([TimeSeriesMomentum(lookback)])
    return engine.run(HistoricalBarFeed({"TEST": series(closes)})).signals


def test_signals_only_on_first_trading_day_of_each_month():
    signals = run([100 + i for i in range(70)])
    assert [s.ts.date() for s in signals] == MONTH_STARTS
    assert all(s.action == SignalAction.BUY for s in signals)


def test_falling_prices_signal_flat():
    signals = run([200 - i for i in range(70)])
    assert [s.ts.date() for s in signals] == MONTH_STARTS
    assert all(s.action == SignalAction.SELL for s in signals)


def test_zero_return_counts_as_flat():
    signals = run([100] * 70)
    assert [s.action for s in signals] == [SignalAction.SELL, SignalAction.SELL]


def test_no_signal_until_full_lookback_is_available():
    assert run([100 + i for i in range(40)], lookback=60) == []


def test_signal_uses_the_close_and_has_no_stops():
    first = run([100 + i for i in range(70)])[0]
    assert first.price == Decimal("131")
    assert first.stop_loss is None
    assert first.take_profit is None
    assert first.strategy_id == "tsmom_3"
    assert "3-day return" in first.reason


def test_invalid_lookback_rejected():
    with pytest.raises(ValueError):
        TimeSeriesMomentum(0)
