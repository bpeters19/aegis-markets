"""Runs a pre-registered hypothesis and judges it mechanically against its criteria."""
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal

from app.backtest.metrics import CurveStats, summarize
from app.backtest.run import num, pct
from app.backtest.service import BacktestOutput, run_strategy_backtest
from app.market_data.domain import Bar
from app.portfolio.engine import ClosedTrade
from app.research.config import Criteria, HypothesisConfig
from app.strategies.time_series_momentum import TimeSeriesMomentum

STRATEGIES = {"time_series_momentum": TimeSeriesMomentum}


@dataclass(frozen=True)
class CriterionResult:
    group: str  # "return" (at least one must pass) or "robustness" (all must pass)
    name: str
    measured: str
    passed: bool


@dataclass(frozen=True)
class SubperiodResult:
    name: str
    strategy_sharpe: float | None
    benchmark_sharpe: float | None


@dataclass(frozen=True)
class EvaluationResult:
    hypothesis_id: str
    title: str
    phase: str
    generated_at: str
    commit: str
    data_hash: str
    config_hash: str
    registered_config_hash: str
    holdout_unlocks: int
    run_ids: dict[str, str]
    period_start: date
    period_end: date
    universe: tuple[str, ...]
    benchmark_name: str
    cash_rate: Decimal
    strategy: CurveStats
    benchmark: CurveStats | None
    correlation: float | None
    average_exposure: float | None
    closed_trades: int
    robustness: dict[str, float | None]
    subperiods: list[SubperiodResult]
    best_trade_share: float | None
    top5_trade_share: float | None
    criteria: list[CriterionResult]
    passed: bool


def at(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def slice_stats(start_value: Decimal, curve: list[tuple[date, Decimal]], start: date, end: date, rf: float) -> CurveStats | None:
    part = [(d, v) for d, v in curve if start <= d < end]
    if not part:
        return None
    before = [v for d, v in curve if d < start]
    return summarize(before[-1] if before else start_value, part, rf)


def concentration(trades: Sequence[ClosedTrade]) -> tuple[float | None, float | None]:
    nets = sorted((float(t.net_pnl) for t in trades), reverse=True)
    total = sum(nets)
    if not nets or total <= 0:
        return None, None
    return max(nets[0], 0.0) / total, sum(n for n in nets[:5] if n > 0) / total


def judge(
    c: Criteria,
    strategy: CurveStats,
    benchmark: CurveStats | None,
    correlation: float | None,
    robustness: dict[str, float | None],
    subperiod_sharpes: Sequence[float | None],
    best_share: float | None,
) -> tuple[list[CriterionResult], bool]:
    s = strategy.sharpe
    b = benchmark.sharpe if benchmark else None
    s_dd = abs(strategy.drawdown.max_drawdown)
    b_dd = abs(benchmark.drawdown.max_drawdown) if benchmark else None
    results: list[CriterionResult] = []

    results.append(CriterionResult(
        "return", "Sharpe ratio higher than benchmark", f"{num(s)} vs {num(b)}",
        s is not None and b is not None and s > b,
    ))
    results.append(CriterionResult(
        "return",
        f"Sharpe within {c.sharpe_tolerance:.2f} of benchmark and max drawdown under "
        f"{c.max_drawdown_ratio:.0%} of benchmark's",
        f"Sharpe {num(s)} vs {num(b)}, drawdown {pct(-s_dd)} vs {pct(-b_dd) if b_dd is not None else 'n/a'}",
        s is not None and b is not None and b_dd is not None
        and s >= b - c.sharpe_tolerance and s_dd < c.max_drawdown_ratio * b_dd,
    ))
    results.append(CriterionResult(
        "return",
        f"Correlation below {c.max_correlation} and Sharpe above {c.min_uncorrelated_sharpe}",
        f"correlation {num(correlation)}, Sharpe {num(s)}",
        correlation is not None and s is not None
        and correlation < c.max_correlation and s > c.min_uncorrelated_sharpe,
    ))
    results.append(CriterionResult(
        "robustness",
        f"Every robustness variant has a Sharpe of at least {c.min_robustness_sharpe}",
        ", ".join(f"{k} {num(v)}" for k, v in robustness.items()) or "none",
        all(v is not None and v >= c.min_robustness_sharpe for v in robustness.values()),
    ))
    positive = sum(1 for v in subperiod_sharpes if v is not None and v > 0)
    results.append(CriterionResult(
        "robustness",
        f"Positive Sharpe in at least {c.min_positive_subperiods} of {len(subperiod_sharpes)} sub-periods",
        f"{positive} of {len(subperiod_sharpes)}",
        positive >= c.min_positive_subperiods,
    ))
    results.append(CriterionResult(
        "robustness",
        f"Best trade under {c.max_best_trade_share:.0%} of net profit",
        pct(best_share, False) if best_share is not None else "n/a (no net profit)",
        best_share is not None and best_share < c.max_best_trade_share,
    ))

    passed = any(r.passed for r in results if r.group == "return") and all(
        r.passed for r in results if r.group == "robustness"
    )
    return results, passed


def run_variant(config: HypothesisConfig, series: dict[str, list[Bar]], lookback_days: int, start: date, end: date) -> BacktestOutput:
    strategy = STRATEGIES[config.strategy](lookback_days)
    return run_strategy_backtest(
        series, series[config.benchmark], [strategy], at(start), at(end), config.capital, config.cash_rate,
        limits=config.limits, costs=config.costs,
        warmup=max(strategy.lookback, config.volatility_lookback + 1),
        volatility_lookback=config.volatility_lookback,
    )


def evaluate_development(
    config: HypothesisConfig,
    series: dict[str, list[Bar]],
    fingerprints: dict[str, object],
) -> EvaluationResult:
    dev = config.development
    rf = float(config.cash_rate)

    print(f"Running {config.primary.name} (primary) {dev.start} to {dev.end} ...", flush=True)
    primary = run_variant(config, series, config.primary.lookback_days, dev.start, dev.end)
    runs = {config.primary.name: primary}
    for variant in config.robustness:
        print(f"Running {variant.name} (robustness) ...", flush=True)
        runs[variant.name] = run_variant(config, series, variant.lookback_days, dev.start, dev.end)

    subperiods = []
    for p in config.subperiods:
        strat = slice_stats(primary.starting_value, primary.curve, p.start, p.end, rf)
        bench = slice_stats(primary.starting_value, primary.benchmark_curve, p.start, p.end, rf)
        subperiods.append(SubperiodResult(p.name, strat.sharpe if strat else None, bench.sharpe if bench else None))

    best, top5 = concentration(primary.trades)
    robustness = {v.name: runs[v.name].strategy.sharpe for v in config.robustness}
    criteria, passed = judge(
        config.criteria, primary.strategy, primary.benchmark, primary.relative.correlation,
        robustness, [s.strategy_sharpe for s in subperiods], best,
    )
    exposure = statistics.fmean(float(x) for _, x in primary.exposure) if primary.exposure else None

    return EvaluationResult(
        hypothesis_id=config.id,
        title=config.title,
        phase="development",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        commit=str(fingerprints["commit"]),
        data_hash=str(fingerprints["data_hash"]),
        config_hash=str(fingerprints["config_hash"]),
        registered_config_hash=str(fingerprints["registered_config_hash"]),
        holdout_unlocks=int(fingerprints["holdout_unlocks"]),
        run_ids={name: run.run_id for name, run in runs.items()},
        period_start=dev.start,
        period_end=dev.end,
        universe=config.universe,
        benchmark_name=config.benchmark,
        cash_rate=config.cash_rate,
        strategy=primary.strategy,
        benchmark=primary.benchmark,
        correlation=primary.relative.correlation,
        average_exposure=exposure,
        closed_trades=primary.trade_summary.count,
        robustness=robustness,
        subperiods=subperiods,
        best_trade_share=best,
        top5_trade_share=top5,
        criteria=criteria,
        passed=passed,
    )
