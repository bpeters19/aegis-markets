from decimal import Decimal

from app.risk.engine import RiskEngine
from app.risk.limits import RiskLimits
from tests.test_risk_engine import buy, portfolio

VOL_LIMITS = RiskLimits(
    sizing_mode="volatility",
    target_position_volatility=Decimal("0.02"),
    max_position_pct=Decimal("0.5"),
    require_stop_loss=False,
)


def test_sizes_position_to_target_volatility():
    # 2% target / 16% volatility x $100,000 = $12,500 -> 125 shares at $100
    decision = RiskEngine(VOL_LIMITS).evaluate(buy(price="100", stop=None), portfolio(), volatility=0.16)
    assert decision.approved
    assert decision.quantity == 125
    assert decision.notes == ("sized by volatility target",)


def test_calmer_asset_gets_a_larger_position():
    decision = RiskEngine(VOL_LIMITS).evaluate(buy(price="100", stop=None), portfolio(), volatility=0.05)
    assert decision.quantity == 400


def test_very_calm_asset_is_capped_by_max_position():
    decision = RiskEngine(VOL_LIMITS).evaluate(buy(price="100", stop=None), portfolio(), volatility=0.01)
    assert decision.quantity == 500
    assert decision.notes == ("sized by max position size",)


def test_missing_volatility_estimate_rejects_the_entry():
    decision = RiskEngine(VOL_LIMITS).evaluate(buy(price="100", stop=None), portfolio(), volatility=None)
    assert not decision.approved
    assert any("no volatility estimate" in r for r in decision.reasons)


def test_default_stop_sizing_ignores_volatility():
    decision = RiskEngine().evaluate(buy(price="100", stop="95"), portfolio(), volatility=0.01)
    assert decision.quantity == 100
    assert decision.notes == ("sized by max position size",)
