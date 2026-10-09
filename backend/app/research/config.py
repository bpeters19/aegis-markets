"""Locked research configurations. A config fully defines how a hypothesis is run and judged;
its content hash identifies it in every report."""
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.execution.costs import CostModel
from app.risk.limits import RiskLimits


@dataclass(frozen=True)
class Period:
    name: str
    start: date
    end: date | None  # None means "through the latest available data"


@dataclass(frozen=True)
class Variant:
    name: str
    lookback_days: int


@dataclass(frozen=True)
class Criteria:
    """The default success criteria from hypotheses.md, as thresholds the evaluator applies."""

    sharpe_tolerance: float = 0.10
    max_drawdown_ratio: float = 0.5
    max_correlation: float = 0.3
    min_uncorrelated_sharpe: float = 0.5
    min_robustness_sharpe: float = 0.0
    min_positive_subperiods: int = 2
    max_best_trade_share: float = 0.25


@dataclass(frozen=True)
class HypothesisConfig:
    id: str
    title: str
    strategy: str
    universe: tuple[str, ...]
    benchmark: str
    primary: Variant
    robustness: tuple[Variant, ...]
    development: Period
    subperiods: tuple[Period, ...]
    holdout: Period
    capital: Decimal
    cash_rate: Decimal
    limits: RiskLimits
    costs: CostModel
    volatility_lookback: int
    criteria: Criteria


def _default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"cannot fingerprint a {type(value).__name__}")


def canonical_json(config: HypothesisConfig) -> str:
    """Same config in, same text out: sorted keys, no whitespace, explicit types."""
    return json.dumps(asdict(config), default=_default, sort_keys=True, separators=(",", ":"))


def config_hash(config: HypothesisConfig) -> str:
    return hashlib.sha256(canonical_json(config).encode()).hexdigest()[:12]
