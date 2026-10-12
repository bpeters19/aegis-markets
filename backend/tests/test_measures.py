from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.backtest.service import run_strategy_backtest
from app.portfolio.engine import ClosedTrade
from app.research.measures import concentration_total
from app.strategies.ma_crossover import MovingAverageCrossover
from tests.test_pipeline_integration import BASE, SETUP, bars


def trade(net):
    opened = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ClosedTrade("AAA", opened, opened + timedelta(days=1), 10, Decimal("100"), Decimal("100"),
                       Decimal(str(net)), Decimal("0"), "test")


def test_closed_trades_only_matches_the_simple_case():
    best, top5 = concentration_total([trade(300), trade(-100), trade(100)], {})
    assert best == pytest.approx(1.0)
    assert top5 == pytest.approx(4 / 3)


def test_open_positions_count_toward_total_profit():
    best, _ = concentration_total([trade(100), trade(100)], {"GLD": Decimal("800")})
    assert best == pytest.approx(0.8)


def test_no_total_profit_means_undefined():
    assert concentration_total([trade(-100)], {"GLD": Decimal("50")}) == (None, None)


@pytest.mark.integration
def test_backtest_reports_profit_on_positions_still_open():
    series = {"AAA": bars("AAA", SETUP + [(13, 13.5, 12.8, 13.4)])}
    out = run_strategy_backtest(
        series, series["AAA"], [MovingAverageCrossover(2, 3)],
        BASE, BASE + timedelta(days=6), Decimal("100000"), Decimal("0"),
    )
    # bought 769 at 13.01 (open + slippage), marked at 13.40, minus $3.85 commission
    assert out.open_positions == {"AAA": 769}
    assert out.open_pnl == {"AAA": Decimal("296.06")}
