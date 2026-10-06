import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from app.backtest.metrics import (
    cagr, daily_returns, max_drawdown, relative_stats, sharpe, sortino, trade_stats,
)
from app.portfolio.engine import ClosedTrade


def curve(values):
    return [(date(2026, 1, 1) + timedelta(days=i), D(str(v))) for i, v in enumerate(values)]


def test_daily_returns_measure_day_one_against_starting_value():
    assert daily_returns(D("100"), curve([110, 99])) == pytest.approx([0.10, -0.10])


def test_cagr_annualizes_by_trading_days():
    assert cagr(100.0, 110.0, 252) == pytest.approx(0.10)
    assert cagr(100.0, 121.0, 504) == pytest.approx(0.10)


def test_max_drawdown_peak_trough_and_recovery():
    dd = max_drawdown(curve([100, 120, 90, 110, 130]))
    assert dd.max_drawdown == pytest.approx(-0.25)
    assert (dd.peak, dd.trough, dd.recovered) == (date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 5))
    assert dd.duration_days == 3


def test_unrecovered_drawdown_runs_to_end_of_data():
    dd = max_drawdown(curve([100, 80, 90]))
    assert dd.max_drawdown == pytest.approx(-0.20)
    assert dd.recovered is None
    assert dd.duration_days == 2


def test_sharpe_and_sortino_match_hand_calculation():
    # returns [0.02, 0.00]: mean 0.01, sample stdev 0.02/sqrt(2) -> 0.7071 daily -> x sqrt(252) = 11.225
    assert sharpe([0.02, 0.0]) == pytest.approx(11.2250, rel=1e-4)
    # returns [0.02, -0.01]: mean 0.005, downside deviation sqrt(0.0001/2) -> 0.7071 daily -> 11.225
    assert sortino([0.02, -0.01]) == pytest.approx(11.2250, rel=1e-4)


def test_ratios_are_undefined_without_volatility():
    assert sharpe([0.01, 0.01]) is None
    assert sortino([0.01, 0.02]) is None


def test_beta_correlation_and_alpha():
    benchmark = [0.01, -0.02, 0.03, 0.0]
    stats = relative_stats([r * 0.5 for r in benchmark], benchmark)
    assert stats.beta == pytest.approx(0.5)
    assert stats.correlation == pytest.approx(1.0)
    assert stats.alpha == pytest.approx(0.0, abs=1e-12)


def make_trade(net, days=2):
    opened = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ClosedTrade("AAA", opened, opened + timedelta(days=days), 10, D("100"), D("100"),
                       D(str(net)), D("0"), "test")


def test_trade_stats():
    stats = trade_stats([make_trade(300), make_trade(-100), make_trade(-100), make_trade(100)])
    assert (stats.count, stats.wins, stats.losses) == (4, 2, 2)
    assert stats.win_rate == pytest.approx(0.5)
    assert stats.payoff_ratio == pytest.approx(2.0)
    assert stats.profit_factor == pytest.approx(2.0)
    assert stats.expectancy == pytest.approx(50.0)
    assert stats.avg_holding_days == pytest.approx(2.0)
    assert stats.best_trade_share == pytest.approx(1.5)
