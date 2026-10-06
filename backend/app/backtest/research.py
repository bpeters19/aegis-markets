"""Research tools: parameter sweeps, holdout (train/test split) and walk-forward testing."""
import argparse
import itertools
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.backtest.metrics import CurveStats, TradeStats, buy_and_hold_curve, summarize, trade_stats
from app.backtest.run import load, num, pct
from app.database.session import get_engine
from app.market_data.domain import Bar
from app.market_data.ingest import parse_utc
from app.strategies.ma_crossover import MovingAverageCrossover
from app.trading.pipeline import TradingPipeline

UTC = timezone.utc
FAST = (5, 10, 20)
SLOW = (30, 50, 100, 200)
HEADER = f"{'params':<14} {'return':>9} {'CAGR':>9} {'Sharpe':>7} {'max DD':>9} {'exposure':>9} {'trades':>7} {'PF':>6}"


@dataclass(frozen=True)
class RunResult:
    fast: int
    slow: int
    stats: CurveStats
    trades: TradeStats
    exposure: float | None
    benchmark: CurveStats | None


def window(bars: list[Bar], start: datetime, end: datetime, warmup: int) -> list[Bar]:
    """Bars in [start, end) plus `warmup` bars before start so indicators are ready on day one."""
    first = next((i for i, b in enumerate(bars) if b.ts >= start), len(bars))
    last = next((i for i, b in enumerate(bars) if b.ts >= end), len(bars))
    return list(bars[max(0, first - warmup):last])


def backtest(series, fast, slow, start, end, capital, rate, benchmark_bars) -> RunResult:
    sliced = {s: window(b, start, end, slow + 1) for s, b in series.items()}
    sliced = {s: b for s, b in sliced.items() if b}

    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        pipeline = TradingPipeline(
            session, [MovingAverageCrossover(fast, slow)],
            starting_cash=capital, cash_rate=rate, trade_from=start,
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
    exposure = [float(x) for d, x in pf.exposure_curve if d >= first_day]

    stats = summarize(starting_value, curve, float(rate))
    bench_bars = [b for b in benchmark_bars if start <= b.ts < end]
    bench_curve = buy_and_hold_curve(bench_bars, starting_value, [d for d, _ in curve])
    bench = summarize(starting_value, bench_curve, float(rate)) if bench_curve and len(bench_curve) == len(curve) else None
    return RunResult(fast, slow, stats, trade_stats(pf.trades), statistics.fmean(exposure) if exposure else None, bench)


def sharpe_key(result: RunResult) -> float:
    return result.stats.sharpe if result.stats.sharpe is not None else float("-inf")


def sweep(series, start, end, capital, rate, bench) -> list[RunResult]:
    results = [
        backtest(series, fast, slow, start, end, capital, rate, bench)
        for fast, slow in itertools.product(FAST, SLOW)
        if fast < slow
    ]
    return sorted(results, key=sharpe_key, reverse=True)


def row(label: str, r: RunResult) -> str:
    s, t = r.stats, r.trades
    return (f"{label:<14} {pct(s.total_return):>9} {pct(s.cagr):>9} {num(s.sharpe):>7} "
            f"{pct(s.drawdown.max_drawdown):>9} {pct(r.exposure, False):>9} {t.count:>7} {num(t.profit_factor):>6}")


def bench_row(name: str, b: CurveStats | None) -> str:
    if b is None:
        return f"{name:<14} n/a"
    return (f"{name:<14} {pct(b.total_return):>9} {pct(b.cagr):>9} {num(b.sharpe):>7} "
            f"{pct(b.drawdown.max_drawdown):>9} {'100.00%':>9}")


def compound(returns) -> float:
    return math.prod(1 + r for r in returns) - 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Parameter sweeps, holdout and walk-forward tests")
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--capital", type=Decimal, default=Decimal("100000"))
    parser.add_argument("--rate", type=Decimal, default=Decimal("0.02"),
                        help="annual rate earned on idle cash, also used as the Sharpe risk-free rate")
    parser.add_argument("--benchmark", default="SPY")
    sub = parser.add_subparsers(dest="command", required=True)

    sw = sub.add_parser("sweep", parents=[shared])
    sw.add_argument("--start", type=parse_utc, required=True)
    sw.add_argument("--end", type=parse_utc, required=True)

    ho = sub.add_parser("holdout", parents=[shared])
    ho.add_argument("--train-start", type=parse_utc, required=True)
    ho.add_argument("--split", type=parse_utc, required=True)
    ho.add_argument("--test-end", type=parse_utc, required=True)

    wf = sub.add_parser("walkforward", parents=[shared])
    wf.add_argument("--first-year", type=int, required=True)
    wf.add_argument("--last-year", type=int, required=True)
    wf.add_argument("--train-years", type=int, default=3)
    args = parser.parse_args()

    if args.command == "sweep":
        lo, hi = args.start, args.end
    elif args.command == "holdout":
        lo, hi = args.train_start, args.test_end
    else:
        lo, hi = datetime(args.first_year, 1, 1, tzinfo=UTC), datetime(args.last_year + 1, 1, 1, tzinfo=UTC)

    series = load(args.symbols, lo - timedelta(days=400), hi)
    name = args.benchmark.upper()
    bench = series.get(name) or load([name], lo - timedelta(days=400), hi)[name]
    common = (args.capital, args.rate, bench)
    print(f"Universe: {', '.join(series)} | cash rate and risk-free rate {args.rate:.2%} | grid {len(FAST) * len(SLOW)} sets\n")

    if args.command == "sweep":
        results = sweep(series, args.start, args.end, *common)
        print(HEADER)
        for r in results:
            print(row(f"{r.fast}/{r.slow}", r))
        print(bench_row(f"{name} B&H", results[0].benchmark))
        return

    if args.command == "holdout":
        results = sweep(series, args.train_start, args.split, *common)
        print(f"IN-SAMPLE {args.train_start:%Y-%m-%d} to {args.split:%Y-%m-%d}, ranked by Sharpe")
        print(HEADER)
        for r in results:
            print(row(f"{r.fast}/{r.slow}", r))
        print(bench_row(f"{name} B&H", results[0].benchmark))

        best = results[0]
        oos = backtest(series, best.fast, best.slow, args.split, args.test_end, *common)
        fixed = backtest(series, 10, 30, args.split, args.test_end, *common)
        print(f"\nOUT-OF-SAMPLE {args.split:%Y-%m-%d} to {args.test_end:%Y-%m-%d} (never used for selection)")
        print(HEADER)
        print(row(f"{best.fast}/{best.slow} chosen", oos))
        print(row("10/30 fixed", fixed))
        print(bench_row(f"{name} B&H", oos.benchmark))
        print(f"\nChosen {best.fast}/{best.slow}: Sharpe {num(best.stats.sharpe)} in-sample -> "
              f"{num(oos.stats.sharpe)} out-of-sample")
        return

    print(f"WALK-FORWARD: choose parameters on the previous {args.train_years} years, trade the next year\n")
    print(f"{'year':<6}{'chosen':>8}{'IS Sharpe':>11}{'OOS return':>12}{'OOS Sharpe':>12}"
          f"{'10/30 fixed':>13}{name + ' B&H':>11}")
    folds = []
    for year in range(args.first_year + args.train_years, args.last_year + 1):
        train_start = datetime(year - args.train_years, 1, 1, tzinfo=UTC)
        test_start = datetime(year, 1, 1, tzinfo=UTC)
        test_end = datetime(year + 1, 1, 1, tzinfo=UTC)
        best = sweep(series, train_start, test_start, *common)[0]
        oos = backtest(series, best.fast, best.slow, test_start, test_end, *common)
        fixed = backtest(series, 10, 30, test_start, test_end, *common)
        folds.append((best, oos, fixed))
        spy = oos.benchmark.total_return if oos.benchmark else None
        print(f"{year:<6}{f'{best.fast}/{best.slow}':>8}{num(best.stats.sharpe):>11}{pct(oos.stats.total_return):>12}"
              f"{num(oos.stats.sharpe):>12}{pct(fixed.stats.total_return):>13}{pct(spy):>11}", flush=True)

    wf_total = compound(o.stats.total_return for _, o, _ in folds)
    fixed_total = compound(f.stats.total_return for _, _, f in folds)
    spy_total = compound(o.benchmark.total_return for _, o, _ in folds if o.benchmark)
    in_sample = [b.stats.sharpe for b, _, _ in folds if b.stats.sharpe is not None]
    out_sample = [o.stats.sharpe for _, o, _ in folds if o.stats.sharpe is not None]
    print(f"\nCompounded over {len(folds)} out-of-sample years: walk-forward {pct(wf_total)}   "
          f"fixed 10/30 {pct(fixed_total)}   {name} B&H {pct(spy_total)}")
    if in_sample and out_sample:
        print(f"Average Sharpe of chosen parameters: {statistics.fmean(in_sample):.2f} in-sample -> "
              f"{statistics.fmean(out_sample):.2f} out-of-sample")


if __name__ == "__main__":
    main()
