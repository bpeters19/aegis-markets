"""Backtest service: runs the full pipeline over a period and returns everything a caller needs.
Independent of HTTP so the API, CLIs and the research evaluator all share it."""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.backtest.metrics import (
    CurveStats, RelativeStats, TradeStats, buy_and_hold_curve, daily_returns, relative_stats, summarize, trade_stats,
)
from app.backtest.research import window
from app.database.session import get_engine
from app.execution.costs import CostModel
from app.market_data.domain import Bar
from app.portfolio.engine import ClosedTrade
from app.risk.limits import RiskLimits
from app.strategies.base import Strategy
from app.strategies.ma_crossover import MovingAverageCrossover
from app.trading.pipeline import TradingPipeline


@dataclass(frozen=True)
class BacktestOutput:
    run_id: str
    starting_value: Decimal
    curve: list[tuple[date, Decimal]]
    benchmark_curve: list[tuple[date, Decimal]]
    exposure: list[tuple[date, Decimal]]
    strategy: CurveStats
    benchmark: CurveStats | None
    relative: RelativeStats
    trades: list[ClosedTrade]
    trade_summary: TradeStats
    counts: dict[str, int]
    open_positions: dict[str, int]


def run_strategy_backtest(
    series: dict[str, list[Bar]],
    benchmark_bars: list[Bar],
    strategies: Sequence[Strategy],
    start: datetime,
    end: datetime,
    capital: Decimal,
    cash_rate: Decimal,
    limits: RiskLimits | None = None,
    costs: CostModel | None = None,
    warmup: int | None = None,
    volatility_lookback: int = 20,
) -> BacktestOutput:
    warmup = warmup if warmup is not None else max(s.lookback for s in strategies)
    sliced = {s: window(b, start, end, warmup) for s, b in series.items()}
    sliced = {s: b for s, b in sliced.items() if b}

    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        pipeline = TradingPipeline(
            session, list(strategies), starting_cash=capital, limits=limits, costs=costs,
            cash_rate=cash_rate, trade_from=start, volatility_lookback=volatility_lookback,
        )
        pipeline.run(sliced)
    finally:
        session.close()
        transaction.rollback()
        connection.close()

    pf = pipeline.portfolio
    first_day = start.date()
    curve = [(d, v) for d, v in pf.equity_curve if d >= first_day]
    before = [v for d, v in pf.equity_curve if d < first_day]
    starting_value = before[-1] if before else capital
    exposure = [(d, x) for d, x in pf.exposure_curve if d >= first_day]

    bench_bars = [b for b in benchmark_bars if start <= b.ts < end]
    bench_curve = buy_and_hold_curve(bench_bars, starting_value, [d for d, _ in curve])
    aligned = bool(bench_curve) and len(bench_curve) == len(curve)

    rate = float(cash_rate)
    strategy = summarize(starting_value, curve, rate)
    benchmark = summarize(starting_value, bench_curve, rate) if aligned else None
    relative = (
        relative_stats(daily_returns(starting_value, curve), daily_returns(starting_value, bench_curve))
        if aligned else RelativeStats(None, None, None)
    )
    return BacktestOutput(
        run_id=pipeline.run_id,
        starting_value=starting_value,
        curve=curve,
        benchmark_curve=bench_curve if aligned else [],
        exposure=exposure,
        strategy=strategy,
        benchmark=benchmark,
        relative=relative,
        trades=list(pf.trades),
        trade_summary=trade_stats(pf.trades),
        counts=dict(pipeline.counts),
        open_positions={s: p.quantity for s, p in pf.positions.items()},
    )


def run_backtest(
    series: dict[str, list[Bar]],
    benchmark_bars: list[Bar],
    fast: int,
    slow: int,
    start: datetime,
    end: datetime,
    capital: Decimal,
    cash_rate: Decimal,
) -> BacktestOutput:
    """Moving-average crossover backtest used by the API."""
    return run_strategy_backtest(
        series, benchmark_bars, [MovingAverageCrossover(fast, slow)], start, end, capital, cash_rate,
        warmup=slow + 1,
    )
