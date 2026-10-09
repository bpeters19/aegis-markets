"""H1: time-series momentum across asset classes. Pre-registered 2026-10-09, before any H1 run.
Must match the H1 entry in docs/research/hypotheses.md. Do not edit after results exist."""
from datetime import date
from decimal import Decimal

from app.execution.costs import CostModel
from app.research.config import Criteria, HypothesisConfig, Period, Variant
from app.risk.limits import RiskLimits

H1 = HypothesisConfig(
    id="H1",
    title="Time-series momentum across asset classes",
    strategy="time_series_momentum",
    universe=(
        "SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ",
        "TLT", "IEF", "SHY", "LQD", "HYG", "TIP",
        "GLD", "SLV", "DBC", "UUP",
    ),
    benchmark="SPY",
    primary=Variant("12-month", 252),
    robustness=(Variant("3-month", 63), Variant("6-month", 126)),
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
        target_position_volatility=Decimal("0.01"),
        max_position_pct=Decimal("0.15"),
        max_exposure_pct=Decimal("1"),
        max_open_positions=16,
        require_stop_loss=False,
    ),
    costs=CostModel(),
    volatility_lookback=20,
    criteria=Criteria(),
)
