from datetime import date

import pytest

from app.backtest.metrics import CurveStats, Drawdown
from app.core.config import get_settings
from app.research.config import PortfolioCriteria, config_hash
from app.research.evaluation import SubperiodResult
from app.research.hypotheses.h1 import H1
from app.research.hypotheses.h2 import H2
from app.research.hypotheses.h3 import H3
from app.research.hypotheses.h4 import H4
from app.research.portfolio import first_trading_days, judge_portfolio, satellite_weights, simulate


def test_first_trading_day_of_each_month():
    days = [date(2026, 1, 30), date(2026, 2, 2), date(2026, 2, 3), date(2026, 3, 2)]
    assert first_trading_days(days) == {date(2026, 1, 30), date(2026, 2, 2), date(2026, 3, 2)}


def test_simulate_rebalances_monthly_and_charges_costs():
    dates = [date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 2)]
    returns = {"CORE": [0.10, 0.0, 0.0], "S": [0.0, 0.0, 0.0]}
    curve = simulate(dates, returns, "CORE", 0.5, window=252, cost_bps=10)
    # day 1: allocate 1.0 from cash, pay 0.001, core +10% -> 0.54945 + 0.4995 = 1.04895
    assert curve[0][1] == pytest.approx(1.04895)
    # Feb 2: rebalance trades 0.04995 in total, paying 0.00004995
    assert curve[-1][1] == pytest.approx(1.04890005)


def test_inverse_volatility_split():
    calm, wild = [0.01, -0.01] * 5, [0.02, -0.02] * 5
    weights = satellite_weights({"calm": calm, "wild": wild}, window=10)
    assert weights == pytest.approx({"calm": 2 / 3, "wild": 1 / 3})


def test_equal_split_before_a_full_window():
    weights = satellite_weights({"a": [0.01, -0.01], "b": [0.02, -0.02]}, window=10)
    assert weights == {"a": 0.5, "b": 0.5}


def test_equal_split_when_a_sleeve_held_nothing():
    weights = satellite_weights({"a": [0.0] * 10, "b": [0.02, -0.02] * 5}, window=10)
    assert weights == {"a": 0.5, "b": 0.5}


def test_single_sleeve_takes_the_whole_satellite():
    assert satellite_weights({"only": [0.01, -0.01]}, window=10) == {"only": 1.0}


def stats(sharpe, drawdown):
    return CurveStats(0.1, 0.05, 0.1, sharpe, None, Drawdown(drawdown, None, None, None, 0), None)


GOOD = dict(
    strategy=stats(0.6, -0.30), benchmark=stats(0.5, -0.50),
    robustness={"a": 0.55, "b": 0.52},
    subperiods=[SubperiodResult("p1", 0.6, 0.4), SubperiodResult("p2", 0.5, 0.5), SubperiodResult("p3", 0.1, 0.3)],
)
STRICT = PortfolioCriteria(sharpe_strictly_higher=True, max_drawdown_ratio=0.7)


def test_portfolio_passes_when_all_criteria_met():
    _, passed = judge_portfolio(STRICT, **GOOD)
    assert passed


@pytest.mark.parametrize("change", [
    {"strategy": stats(0.5, -0.30)},
    {"strategy": stats(0.6, -0.40)},
    {"robustness": {"a": 0.55, "b": 0.45}},
    {"subperiods": [SubperiodResult("p1", 0.3, 0.4), SubperiodResult("p2", 0.5, 0.5), SubperiodResult("p3", 0.1, 0.3)]},
])
def test_portfolio_fails_when_any_criterion_is_missed(change):
    _, passed = judge_portfolio(STRICT, **{**GOOD, **change})
    assert not passed


def test_equal_sharpe_passes_when_not_strict():
    loose = PortfolioCriteria(sharpe_strictly_higher=False, max_drawdown_ratio=0.8)
    _, passed = judge_portfolio(loose, **{**GOOD, "strategy": stats(0.5, -0.30)})
    assert passed


def test_portfolios_are_pinned_to_the_tested_sleeves():
    assert dict(H2.sleeve_config_hashes) == {"H1": config_hash(H1)}
    assert dict(H4.sleeve_config_hashes) == {"H1": config_hash(H1), "H3": config_hash(H3)}


def test_portfolios_match_the_preregistration():
    assert (H2.primary.core_weight, sorted(v.core_weight for v in H2.robustness)) == (0.7, [0.6, 0.8])
    assert (H4.primary.core_weight, sorted(v.core_weight for v in H4.robustness)) == (0.6, [0.5, 0.7])
    assert H4.criteria.sharpe_strictly_higher and H4.criteria.max_drawdown_ratio == 0.7
    assert not H2.criteria.sharpe_strictly_higher and H2.criteria.max_drawdown_ratio == 0.8
    assert H2.development.end <= get_settings().research_lock_date
    assert set(H3.universe) <= set(H4.universe)
