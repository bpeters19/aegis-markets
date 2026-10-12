"""H3: short-term mean reversion in equity index ETFs. Pre-registered 2026-10-09, implementation details
clarified 2026-10-12, both before any H3 run. Must match the H3 entry in docs/research/hypotheses.md."""
from datetime import date
from decimal import Decimal

from app.execution.costs import CostModel
from app.research.config import HypothesisConfig, ParamVariant, Period, SatelliteCriteria
from app.risk.limits import RiskLimits

FIXED = (("rsi_period", 2), ("trend_window", 200), ("exit_window", 5), ("max_hold_days", 10))


def variant(name: str, threshold: float) -> ParamVariant:
    return ParamVariant(name, (("entry_threshold", threshold),) + FIXED)


H3 = HypothesisConfig(
    id="H3",
    title="Short-term mean reversion in equity index ETFs",
    strategy="mean_reversion",
    universe=("SPY", "QQQ", "IWM", "EFA", "EEM"),
    benchmark="SPY",
    primary=variant("RSI below 10", 10.0),
    robustness=(variant("RSI below 5", 5.0), variant("RSI below 15", 15.0)),
    development=Period("development", date(2008, 1, 1), date(2023, 1, 1)),
    subperiods=(
        Period("2008-2012", date(2008, 1, 1), date(2013, 1, 1)),
        Period("2013-2017", date(2013, 1, 1), date(2018, 1, 1)),
        Period("2018-2022", date(2018, 1, 1), date(2023, 1, 1)),
    ),
    holdout=Period("locked", date(2023, 1, 1), None),
    capital=Decimal("100000"),
    cash_rate=Decimal("0.02"),
    limits=RiskLimits(
        sizing_mode="volatility",
        target_position_volatility=Decimal("0.02"),
        max_position_pct=Decimal("0.20"),
        max_exposure_pct=Decimal("1"),
        max_open_positions=5,
        require_stop_loss=False,
    ),
    costs=CostModel(),
    volatility_lookback=20,
    criteria=SatelliteCriteria(),
)
