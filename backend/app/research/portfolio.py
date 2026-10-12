"""Portfolio hypotheses (H2, H4): combine a fixed core with tested sleeves at the return level."""
import statistics
from collections.abc import Sequence
from datetime import date, datetime, timezone

from app.backtest.metrics import CurveStats, daily_returns, relative_stats, summarize
from app.backtest.run import num, pct
from app.backtest.service import BacktestOutput
from app.market_data.domain import Bar
from app.research.config import HypothesisConfig, ParamVariant, PortfolioConfig, PortfolioCriteria
from app.research.evaluation import (
    CriterionResult, EvaluationResult, SubperiodResult, run_variant, slice_stats,
)
from app.research.satellite import run_param_variant


def first_trading_days(dates: Sequence[date]) -> set[date]:
    days, previous = set(), None
    for d in dates:
        if previous is None or (d.year, d.month) != (previous.year, previous.month):
            days.add(d)
        previous = d
    return days


def satellite_weights(history: dict[str, list[float]], window: int) -> dict[str, float]:
    """Inverse-volatility split between sleeves over the last `window` daily returns. Equal split when
    any sleeve lacks a full window or had zero volatility (held no positions)."""
    names = list(history)
    equal = {n: 1 / len(names) for n in names}
    if len(names) == 1:
        return {names[0]: 1.0}
    inverse = {}
    for name, returns in history.items():
        if len(returns) < window:
            return equal
        vol = statistics.stdev(returns[-window:])
        if vol == 0:
            return equal
        inverse[name] = 1 / vol
    total = sum(inverse.values())
    return {n: inverse[n] / total for n in names}


def simulate(
    dates: Sequence[date],
    returns: dict[str, list[float]],
    core: str,
    core_weight: float,
    window: int,
    cost_bps: float,
    start_value: float = 1.0,
) -> list[tuple[date, float]]:
    """Daily portfolio value. On each month's first trading day, rebalance using only earlier returns,
    paying cost_bps on the traded amount (including the first allocation from cash)."""
    sleeves = [n for n in returns if n != core]
    rebalance_days = first_trading_days(dates)
    holdings = {n: 0.0 for n in returns}
    cash = start_value
    curve = []
    for i, day in enumerate(dates):
        value = cash + sum(holdings.values())
        if day in rebalance_days:
            split = satellite_weights({n: returns[n][:i] for n in sleeves}, window)
            weights = {core: core_weight, **{n: (1 - core_weight) * split[n] for n in sleeves}}
            traded = sum(abs(weights[n] * value - holdings[n]) for n in returns)
            value -= traded * cost_bps / 10_000
            holdings = {n: weights[n] * value for n in returns}
            cash = 0.0
        for name in returns:
            holdings[name] *= 1 + returns[name][i]
        curve.append((day, cash + sum(holdings.values())))
    return curve


def judge_portfolio(
    c: PortfolioCriteria,
    strategy: CurveStats,
    benchmark: CurveStats,
    robustness: dict[str, float | None],
    subperiods: Sequence[SubperiodResult],
) -> tuple[list[CriterionResult], bool]:
    s, b = strategy.sharpe, benchmark.sharpe
    s_dd, b_dd = abs(strategy.drawdown.max_drawdown), abs(benchmark.drawdown.max_drawdown)
    better = (lambda x: x > b) if c.sharpe_strictly_higher else (lambda x: x >= b)
    at_least = sum(
        1 for p in subperiods
        if p.strategy_sharpe is not None and p.benchmark_sharpe is not None and p.strategy_sharpe >= p.benchmark_sharpe
    )
    rows = [
        CriterionResult(
            "required", f"Sharpe ratio {'higher than' if c.sharpe_strictly_higher else 'at least as high as'} benchmark",
            f"{num(s)} vs {num(b)}", s is not None and b is not None and better(s),
        ),
        CriterionResult(
            "required", f"Max drawdown no more than {c.max_drawdown_ratio:.0%} of benchmark's",
            f"{pct(-s_dd)} vs {pct(-b_dd)} ({s_dd / b_dd:.0%} of benchmark)" if b_dd else "n/a",
            b_dd > 0 and s_dd <= c.max_drawdown_ratio * b_dd,
        ),
        CriterionResult(
            "required",
            f"Sharpe at least as high as benchmark in at least {c.min_subperiods_at_least_benchmark} of {len(subperiods)} sub-periods",
            f"{at_least} of {len(subperiods)}", at_least >= c.min_subperiods_at_least_benchmark,
        ),
        CriterionResult(
            "required", "Every robustness variant has a Sharpe at least as high as benchmark",
            ", ".join(f"{k} {num(v)}" for k, v in robustness.items()),
            b is not None and all(v is not None and v >= b for v in robustness.values()),
        ),
    ]
    return rows, all(r.passed for r in rows)


def run_sleeve(sleeve: HypothesisConfig, series: dict[str, list[Bar]], start: date, end: date) -> BacktestOutput:
    own = {s: series[s] for s in sleeve.universe}
    if isinstance(sleeve.primary, ParamVariant):
        return run_param_variant(sleeve, own, sleeve.primary, start, end)
    return run_variant(sleeve, own, sleeve.primary.lookback_days, start, end)


def evaluate_portfolio_development(
    config: PortfolioConfig,
    series: dict[str, list[Bar]],
    fingerprints: dict[str, object],
    sleeve_configs: dict[str, HypothesisConfig],
) -> EvaluationResult:
    dev = config.development
    rf = float(config.cash_rate)
    runs = {}
    for sleeve_id in config.sleeves:
        print(f"Running sleeve {sleeve_id} ({sleeve_configs[sleeve_id].primary.name}) {dev.start} to {dev.end} ...", flush=True)
        runs[sleeve_id] = run_sleeve(sleeve_configs[sleeve_id], series, dev.start, dev.end)
        print(f"  {sleeve_id} sleeve Sharpe {num(runs[sleeve_id].strategy.sharpe)}", flush=True)

    first = runs[config.sleeves[0]]
    dates = [d for d, _ in first.curve]
    start_value = float(first.starting_value)
    benchmark_curve = [(d, float(v)) for d, v in first.benchmark_curve]
    returns = {config.core: daily_returns(start_value, benchmark_curve)}
    for sleeve_id, run in runs.items():
        if [d for d, _ in run.curve] != dates:
            raise RuntimeError(f"sleeve {sleeve_id} has a different trading calendar")
        returns[sleeve_id] = daily_returns(run.starting_value, run.curve)

    curves = {
        v.name: simulate(dates, returns, config.core, v.core_weight, config.vol_window, config.cost_bps, start_value)
        for v in (config.primary, *config.robustness)
    }
    primary_curve = curves[config.primary.name]
    strategy = summarize(start_value, primary_curve, rf)
    benchmark = summarize(start_value, benchmark_curve, rf)
    relative = relative_stats(daily_returns(start_value, primary_curve), daily_returns(start_value, benchmark_curve))
    robustness = {v.name: summarize(start_value, curves[v.name], rf).sharpe for v in config.robustness}

    subperiods = []
    for p in config.subperiods:
        strat = slice_stats(start_value, primary_curve, p.start, p.end, rf)
        bench = slice_stats(start_value, benchmark_curve, p.start, p.end, rf)
        subperiods.append(SubperiodResult(p.name, strat.sharpe if strat else None, bench.sharpe if bench else None))

    criteria, passed = judge_portfolio(config.criteria, strategy, benchmark, robustness, subperiods)
    return EvaluationResult(
        hypothesis_id=config.id, title=config.title, phase="development",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        commit=str(fingerprints["commit"]), data_hash=str(fingerprints["data_hash"]),
        config_hash=str(fingerprints["config_hash"]),
        registered_config_hash=str(fingerprints["registered_config_hash"]),
        holdout_unlocks=int(fingerprints["holdout_unlocks"]),
        run_ids={f"sleeve {sid}": run.run_id for sid, run in runs.items()},
        period_start=dev.start, period_end=dev.end, universe=config.universe,
        benchmark_name=config.benchmark, cash_rate=config.cash_rate,
        strategy=strategy, benchmark=benchmark, correlation=relative.correlation,
        average_exposure=None, closed_trades=sum(r.trade_summary.count for r in runs.values()),
        robustness=robustness, subperiods=subperiods, best_trade_share=None, top5_trade_share=None,
        criteria=criteria, passed=passed, concentration_basis="not judged for portfolio hypotheses",
    )
