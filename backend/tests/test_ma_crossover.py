from decimal import Decimal

import pytest

from app.engine.engine import SignalEngine
from app.engine.events import SignalAction
from app.engine.feed import HistoricalBarFeed
from app.strategies.ma_crossover import MovingAverageCrossover
from tests.factories import series


def run(closes, fast=2, slow=3):
    engine = SignalEngine([MovingAverageCrossover(fast, slow)])
    return engine.run(HistoricalBarFeed({"TEST": series(closes)})).signals


def test_golden_cross_emits_buy_with_tick_rounded_stop_and_target():
    closes = [10, 10, 10, 10, 13]
    signals = run(closes)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.action == SignalAction.BUY
    assert signal.price == Decimal("13")
    assert signal.stop_loss == Decimal("12.35")
    assert signal.take_profit == Decimal("14.30")
    assert signal.ts == series(closes)[4].ts


def test_death_cross_emits_sell():
    signals = run([10, 10, 10, 10, 7])
    assert [s.action for s in signals] == [SignalAction.SELL]
    assert signals[0].stop_loss is None


def test_no_signal_without_a_cross_or_enough_history():
    assert run([10] * 10) == []
    assert run([10, 13]) == []


def test_replay_is_deterministic():
    closes = [10, 12, 9, 14, 8, 15, 7, 16, 10, 11, 13, 9]
    first = run(closes)
    assert len(first) > 0
    assert first == run(closes)


def test_invalid_windows_rejected():
    with pytest.raises(ValueError):
        MovingAverageCrossover(fast=30, slow=10)
