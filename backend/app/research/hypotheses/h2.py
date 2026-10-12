"""H2: stocks plus a trend-following sleeve. Pre-registered 2026-10-09; implementation details clarified
2026-10-12 before any run. Must match the H2 entry in docs/research/hypotheses.md."""
from decimal import Decimal

from app.research.config import PortfolioConfig, PortfolioCriteria, WeightVariant
from app.research.hypotheses.h1 import H1

H2 = PortfolioConfig(
    id="H2",
    title="Stocks plus a trend-following sleeve",
    core="SPY",
    sleeves=("H1",),
    sleeve_config_hashes=(("H1", "ef3096ca90c3"),),
    universe=H1.universe,
    benchmark="SPY",
    primary=WeightVariant("70% SPY, 30% trend", 0.7),
    robustness=(WeightVariant("80% SPY, 20% trend", 0.8), WeightVariant("60% SPY, 40% trend", 0.6)),
    development=H1.development,
    subperiods=H1.subperiods,
    cash_rate=Decimal("0.02"),
    rebalance="first trading day of each month",
    cost_bps=5.0,
    vol_window=252,
    criteria=PortfolioCriteria(sharpe_strictly_higher=False, max_drawdown_ratio=0.8),
)
