"""Evaluation for satellite hypotheses (H3 and later). H1's evaluation path stays frozen."""
import statistics
from collections.abc import Sequence

from app.backtest.metrics import CurveStats
from app.backtest.run import num, pct
from app.backtest.service import BacktestOutput, run_strategy_backtest
from app.market_data.domain import Bar
from app.research.config import HypothesisConfig, ParamVariant, SatelliteCriteria
from app.research.evaluation import (
    CriterionResult, EvaluationResult, SubperiodResult, at, slice_stats,
)
from app.research.measures import concentration_total
from app.strategies.base import Strategy
from app.strategies.mean_reversion import MeanReversion

BUILDERS = {"mean_reversion": lambda params: MeanReversion(**params)}


def build_strategy(config: HypothesisConfig, variant: ParamVariant) -> Strategy:
    return BUILDERS[config.strategy](dict(variant.params))


def run_param_variant(config, series: dict[str, list[Bar]], variant: ParamVariant, start, end) -> BacktestOutput:
    strategy = build_strategy(config, variant)
    return run_strategy_backtest(
        series, series[config.benchmark], [strategy], at(start), at(end), config.capital, config.cash_rate,
        limits=config.limits, costs=config.costs,
        warmup=max(strategy.lookback, config.volatility_lookback + 1),
        volatility_lookback=config.volatility_lookback,
    )


def judge_satellite(
    c: SatelliteCriteria,
    strategy: CurveStats,
    correlation: float | None,
    profit_factor: float | None,
    trades: int,
    best_share: float | None,
    robustness: dict[str, float | None],
    subperiod_sharpes: Sequence[float | None],
    min_trades: int | None = None,
    include_development_checks: bool = True,
) -> tuple[list[CriterionResult], bool]:
    s = strategy.sharpe
    needed = c.min_trades if min_trades is None else min_trades
    rows = [
        CriterionResult("required", f"Sharpe ratio above {c.min_sharpe}", num(s),
                        s is not None and s > c.min_sharpe),
        CriterionResult("required", f"Correlation to benchmark below {c.max_correlation}", num(correlation),
                        correlation is not None and correlation < c.max_correlation),
        CriterionResult("required", f"Profit factor above {c.min_profit_factor}", num(profit_factor),
                        profit_factor is not None and profit_factor > c.min_profit_factor),
        CriterionResult("required", f"At least {needed} closed trades", str(trades), trades >= needed),
        CriterionResult("required",
                        f"Best contribution under {c.max_best_share_total:.0%} of total profit including open positions",
                        pct(best_share, False) if best_share is not None else "n/a (no total profit)",
                        best_share is not None and best_share < c.max_best_share_total),
    ]
    if include_development_checks:
        rows.append(CriterionResult(
            "required", f"Every robustness variant has a Sharpe ratio above {c.robustness_sharpe_above}",
            ", ".join(f"{k} {num(v)}" for k, v in robustness.items()) or "none",
            all(v is not None and v > c.robustness_sharpe_above for v in robustness.values()),
        ))
        positive = sum(1 for v in subperiod_sharpes if v is not None and v > 0)
        rows.append(CriterionResult(
            "required", f"Positive Sharpe in at least {c.min_positive_subperiods} of {len(subperiod_sharpes)} sub-periods",
            f"{positive} of {len(subperiod_sharpes)}", positive >= c.min_positive_subperiods,
        ))
    return rows, all(r.passed for r in rows)


def evaluate_satellite_development(
    config: HypothesisConfig, series: dict[str, list[Bar]], fingerprints: dict[str, object]
) -> EvaluationResult:
    from datetime import datetime, timezone

    dev = config.development
    rf = float(config.cash_rate)
    print(f"Running {config.primary.name} (primary) {dev.start} to {dev.end} ...", flush=True)
    primary = run_param_variant(config, series, config.primary, dev.start, dev.end)
    runs = {config.primary.name: primary}
    for v in config.robustness:
        print(f"Running {v.name} (robustness) ...", flush=True)
        runs[v.name] = run_param_variant(config, series, v, dev.start, dev.end)

    subperiods = []
    for p in config.subperiods:
        strat = slice_stats(primary.starting_value, primary.curve, p.start, p.end, rf)
        bench = slice_stats(primary.starting_value, primary.benchmark_curve, p.start, p.end, rf)
        subperiods.append(SubperiodResult(p.name, strat.sharpe if strat else None, bench.sharpe if bench else None))

    best, top5 = concentration_total(primary.trades, primary.open_pnl)
    robustness = {v.name: runs[v.name].strategy.sharpe for v in config.robustness}
    t = primary.trade_summary
    criteria, passed = judge_satellite(
        config.criteria, primary.strategy, primary.relative.correlation, t.profit_factor, t.count,
        best, robustness, [s.strategy_sharpe for s in subperiods],
    )
    exposure = statistics.fmean(float(x) for _, x in primary.exposure) if primary.exposure else None
    return EvaluationResult(
        hypothesis_id=config.id, title=config.title, phase="development",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        commit=str(fingerprints["commit"]), data_hash=str(fingerprints["data_hash"]),
        config_hash=str(fingerprints["config_hash"]),
        registered_config_hash=str(fingerprints["registered_config_hash"]),
        holdout_unlocks=int(fingerprints["holdout_unlocks"]),
        run_ids={name: run.run_id for name, run in runs.items()},
        period_start=dev.start, period_end=dev.end, universe=config.universe,
        benchmark_name=config.benchmark, cash_rate=config.cash_rate,
        strategy=primary.strategy, benchmark=primary.benchmark, correlation=primary.relative.correlation,
        average_exposure=exposure, closed_trades=t.count, robustness=robustness, subperiods=subperiods,
        best_trade_share=best, top5_trade_share=top5, criteria=criteria, passed=passed,
        concentration_basis="total profit including open positions",
    )
