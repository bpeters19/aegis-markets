"""H4: combined core-satellite portfolio. Pre-registered 2026-10-09; implementation details clarified
2026-10-12 before any run. Must match the H4 entry in docs/research/hypotheses.md."""
from decimal import Decimal

from app.research.config import PortfolioConfig, PortfolioCriteria, WeightVariant
from app.research.hypotheses.h1 import H1

H4 = PortfolioConfig(
    id="H4",
    title="Combined core-satellite portfolio",
    core="SPY",
    sleeves=("H1", "H3"),
    sleeve_config_hashes=(("H1", "ef3096ca90c3"), ("H3", "88055e63c63c")),
    universe=H1.universe,
    benchmark="SPY",
    primary=WeightVariant("60% SPY, 40% satellite", 0.6),
    robustness=(WeightVariant("70% SPY, 30% satellite", 0.7), WeightVariant("50% SPY, 50% satellite", 0.5)),
    development=H1.development,
    subperiods=H1.subperiods,
    cash_rate=Decimal("0.02"),
    rebalance="first trading day of each month",
    cost_bps=5.0,
    vol_window=252,
    criteria=PortfolioCriteria(sharpe_strictly_higher=True, max_drawdown_ratio=0.7),
)
