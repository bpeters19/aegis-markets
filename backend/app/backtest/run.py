import argparse
import statistics
import time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.backtest.metrics import (
    CurveStats, buy_and_hold_curve, daily_returns, relative_stats, summarize, trade_stats,
)
from app.database.session import get_engine
from app.engine.feed import bar_from_record
from app.market_data.domain import Timeframe
from app.market_data.ingest import parse_utc
from app.market_data.repository import fetch_bars
from app.strategies.ma_crossover import MovingAverageCrossover
from app.risk.limits import RiskLimits
from app.trading.pipeline import TradingPipeline


def pct(x: float | None, signed: bool = True) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.2%}" if signed else f"{x:.2%}"


def num(x: float | None, digits: int = 2) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


def money(x: float | None) -> str:
    return "n/a" if x is None else f"${x:,.2f}"


def load(symbols, start, end):
    with Session(get_engine()) as session:
        return {
            s.upper(): [bar_from_record(r) for r in fetch_bars(session, s, Timeframe.DAY_1, start, end, limit=1_000_000)]
            for s in symbols
        }


def curve_rows(s: CurveStats, b: CurveStats | None):
    def bench(fn):
        return fn(b) if b else "n/a"

    return [
        ("Total return", pct(s.total_return), bench(lambda x: pct(x.total_return))),
        ("CAGR", pct(s.cagr), bench(lambda x: pct(x.cagr))),
        ("Volatility (annualized)", pct(s.volatility, False), bench(lambda x: pct(x.volatility, False))),
        ("Sharpe ratio", num(s.sharpe), bench(lambda x: num(x.sharpe))),
        ("Sortino ratio", num(s.sortino), bench(lambda x: num(x.sortino))),
        ("Max drawdown", pct(s.drawdown.max_drawdown), bench(lambda x: pct(x.drawdown.max_drawdown))),
        ("Drawdown length (days)", str(s.drawdown.duration_days), bench(lambda x: str(x.drawdown.duration_days))),
        ("Calmar ratio", num(s.calmar), bench(lambda x: num(x.calmar))),
    ]


def describe_drawdown(name: str, stats: CurveStats) -> str:
    dd = stats.drawdown
    if dd.peak is None:
        return f"{name}: no drawdown"
    recovery = f"recovered {dd.recovered}" if dd.recovered else "not recovered by end of data"
    return f"{name}: peak {dd.peak} -> trough {dd.trough}, {recovery}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest a strategy with full performance metrics")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--start", type=parse_utc, required=True)
    parser.add_argument("--end", type=parse_utc, required=True)
    parser.add_argument("--capital", type=Decimal, default=Decimal("100000"))
    parser.add_argument("--fast", type=int, default=10)
    parser.add_argument("--slow", type=int, default=30)
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--rf", type=float, default=0.0, help="annual risk-free rate, e.g. 0.04; idle cash earns it too")
    parser.add_argument("--sizing", choices=["stop", "volatility"], default="stop")
    parser.add_argument("--max-position", type=float, default=0.10, help="max fraction of equity per position")
    args = parser.parse_args()

    series = load(args.symbols, args.start, args.end)
    benchmark = args.benchmark.upper()
    bench_bars = series.get(benchmark) or load([benchmark], args.start, args.end)[benchmark]

    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        started = time.perf_counter()
        limits = RiskLimits(sizing_mode=args.sizing, max_position_pct=Decimal(str(args.max_position)))
        pipeline = TradingPipeline(
            session, [MovingAverageCrossover(args.fast, args.slow)],
            starting_cash=args.capital, limits=limits, cash_rate=Decimal(str(args.rf)),
        )
        pipeline.run(series)
        elapsed = time.perf_counter() - started
    finally:
        session.close()
        transaction.rollback()
        connection.close()

    pf = pipeline.portfolio
    curve = pf.equity_curve
    dates = [d for d, _ in curve]
    bench_curve = buy_and_hold_curve(bench_bars, pf.starting_cash, dates)

    s = summarize(pf.starting_cash, curve, args.rf)
    b = summarize(pf.starting_cash, bench_curve, args.rf) if len(bench_curve) == len(curve) else None
    rel = relative_stats(daily_returns(pf.starting_cash, curve), daily_returns(pf.starting_cash, bench_curve))
    t = trade_stats(pf.trades)
    exposure = statistics.fmean(float(x) for _, x in pf.exposure_curve) if pf.exposure_curve else None

    print(f"SMA {args.fast}/{args.slow} on {len(series)} symbols, {dates[0]} to {dates[-1]} "
          f"({len(dates)} trading days, {elapsed:.2f}s, run {pipeline.run_id})\n")
    print(f"{'':<26}{'Strategy':>12}{benchmark + ' B&H':>12}")
    for label, strat, bench in curve_rows(s, b):
        print(f"{label:<26}{strat:>12}{bench:>12}")
    print(f"{'Average exposure':<26}{pct(exposure, False):>12}{'100.00%':>12}")
    print(f"\n{describe_drawdown('Strategy', s)}")
    if b:
        print(describe_drawdown(benchmark, b))

    print(f"\nVs {benchmark}:  beta {num(rel.beta)}   correlation {num(rel.correlation)}   "
          f"alpha (annualized) {pct(rel.alpha)}")

    print(f"\nTrades {t.count}: {t.wins} wins / {t.losses} losses   win rate {pct(t.win_rate, False)}")
    print(f"Average win {money(t.avg_win)}   average loss {money(t.avg_loss)}   payoff ratio {num(t.payoff_ratio)}")
    print(f"Profit factor {num(t.profit_factor)}   expectancy {money(t.expectancy)} per trade   "
          f"average hold {num(t.avg_holding_days, 1)} days")
    print(f"Best single trade = {pct(t.best_trade_share, False)} of net profit from closed trades")

    print(f"\nAssumptions: risk-free rate {args.rf:.2%}; idle cash earns nothing; costs and slippage per CostModel;")
    print("parameters and symbols chosen with hindsight (in-sample). Treat as diagnostics, not evidence.")


if __name__ == "__main__":
    main()
