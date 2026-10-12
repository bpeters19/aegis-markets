from decimal import Decimal

import pytest

from app.backtest.metrics import CurveStats, Drawdown
from app.research.config import SatelliteCriteria, config_hash
from app.research.hypotheses.h1 import H1
from app.research.hypotheses.h3 import H3
from app.research.satellite import build_strategy, judge_satellite
from app.strategies.mean_reversion import MeanReversion
from app.core.config import get_settings

C = SatelliteCriteria()


def stats(sharpe):
    return CurveStats(0.1, 0.05, 0.1, sharpe, None, Drawdown(-0.1, None, None, None, 0), None)


GOOD = dict(strategy=stats(0.8), correlation=0.3, profit_factor=1.5, trades=300, best_share=0.05,
            robustness={"RSI below 5": 0.4, "RSI below 15": 0.6}, subperiod_sharpes=[0.5, 0.2, -0.1])


def test_h1_config_hash_is_unchanged():
    assert config_hash(H1) == "ef3096ca90c3"


def test_passes_when_every_criterion_is_met():
    _, passed = judge_satellite(C, **GOOD)
    assert passed


@pytest.mark.parametrize("change", [
    {"strategy": stats(0.4)},
    {"correlation": 0.6},
    {"profit_factor": 1.2},
    {"trades": 150},
    {"best_share": 0.15},
    {"robustness": {"RSI below 5": 0.0, "RSI below 15": 0.6}},
    {"subperiod_sharpes": [0.5, -0.2, -0.1]},
])
def test_fails_when_any_single_criterion_is_missed(change):
    _, passed = judge_satellite(C, **{**GOOD, **change})
    assert not passed


def test_h3_matches_the_preregistration():
    assert H3.universe == ("SPY", "QQQ", "IWM", "EFA", "EEM")
    assert dict(H3.primary.params)["entry_threshold"] == 10.0
    assert sorted(dict(v.params)["entry_threshold"] for v in H3.robustness) == [5.0, 15.0]
    assert H3.limits.max_position_pct == Decimal("0.20")
    assert H3.development.end <= get_settings().research_lock_date


def test_h3_builds_the_preregistered_strategy():
    strategy = build_strategy(H3, H3.primary)
    assert isinstance(strategy, MeanReversion)
    assert (strategy.entry_threshold, strategy.trend_window, strategy.exit_window, strategy.max_hold_days) == (10.0, 200, 5, 10)
