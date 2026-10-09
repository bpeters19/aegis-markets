from dataclasses import replace
from decimal import Decimal

from app.core.config import get_settings
from app.research.config import Criteria, config_hash
from app.research.hypotheses.h1 import H1


def test_identical_config_has_identical_hash():
    assert config_hash(replace(H1)) == config_hash(H1)


def test_any_change_changes_the_hash():
    assert config_hash(replace(H1, cash_rate=Decimal("0.03"))) != config_hash(H1)
    assert config_hash(replace(H1, criteria=Criteria(max_best_trade_share=0.30))) != config_hash(H1)


def test_h1_never_develops_on_locked_data():
    lock = get_settings().research_lock_date
    assert H1.development.end <= lock
    assert all(p.end <= lock for p in H1.subperiods)
    assert H1.holdout.start == lock


def test_h1_subperiods_tile_the_development_period():
    periods = H1.subperiods
    assert periods[0].start == H1.development.start
    assert all(a.end == b.start for a, b in zip(periods, periods[1:]))
    assert periods[-1].end == H1.development.end


def test_h1_matches_the_preregistration():
    assert H1.primary.lookback_days == 252
    assert {v.lookback_days for v in H1.robustness} == {63, 126}
    assert len(H1.universe) == 16
    assert H1.limits.sizing_mode == "volatility"
    assert H1.limits.target_position_volatility == Decimal("0.01")
    assert H1.limits.max_open_positions == 16
    assert H1.limits.require_stop_loss is False
    assert H1.cash_rate == Decimal("0.02")
