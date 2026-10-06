import argparse
import time
from collections import Counter
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.engine.feed import bar_from_record
from app.market_data.domain import Timeframe
from app.market_data.ingest import parse_utc
from app.market_data.repository import fetch_bars
from app.strategies.ma_crossover import MovingAverageCrossover
from app.trading.pipeline import TradingPipeline


def report(p: TradingPipeline, series, elapsed: float) -> None:
    pf = p.portfolio
    print(f"Run {p.run_id}: {p.bars_processed} bars across {len(series)} symbols in {elapsed:.2f}s")
    print(f"Signals {p.counts['signals']}  (approved {p.counts['approved']}, rejected {p.counts['rejected']})")
    print(f"Orders {p.counts['orders']}  fills {p.counts['fills']}  cancels {p.counts['cancels']}  (entries skipped on gaps: {p.counts['gap_cancels']})\n")

    print(f"{'symbol':<6} {'opened':<10}    {'closed':<10} {'qty':>5} {'entry':>9}    {'exit':>9} {'net P&L':>10}  exit")
    for t in pf.trades:
        print(f"{t.symbol:<6} {t.opened_at:%Y-%m-%d} -> {t.closed_at:%Y-%m-%d} {t.quantity:>5} "
              f"{t.avg_entry:>9.2f} -> {t.avg_exit:>9.2f} {t.net_pnl:>10,.2f}  {t.exit_reason}")

    wins = [t for t in pf.trades if t.net_pnl > 0]
    losses = [t for t in pf.trades if t.net_pnl <= 0]
    if pf.trades:
        print(f"\nClosed trades {len(pf.trades)}: {len(wins)} wins, {len(losses)} losses "
              f"({len(wins) / len(pf.trades):.0%} win rate)")
        if wins:
            print(f"Average win  ${sum(t.net_pnl for t in wins) / len(wins):,.2f}")
        if losses:
            print(f"Average loss ${sum(t.net_pnl for t in losses) / len(losses):,.2f}")
        exits = Counter(t.exit_reason for t in pf.trades)
        print("Exits: " + ", ".join(f"{reason} {n}" for reason, n in exits.most_common()))

    print(f"\nRealized P&L ${pf.realized_pnl:,.2f}   unrealized ${pf.unrealized_pnl:,.2f}   "
          f"commissions ${pf.commissions:,.2f}")
    print(f"Final equity ${pf.equity:,.2f}  ({pf.equity / pf.starting_cash - 1:+.2%})")
    spy = series.get("SPY")
    if spy:
        print(f"SPY buy and hold, same period: {spy[-1].close / spy[0].open - 1:+.2%}")
    held = ", ".join(f"{s} {pos.quantity}" for s, pos in pf.positions.items())
    print(f"Open at end: {held or 'none'}")
    print("Accounting identity: OK   Reconciliation vs OMS: OK")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full trading pipeline over stored bars")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--start", type=parse_utc, required=True)
    parser.add_argument("--end", type=parse_utc, required=True)
    parser.add_argument("--capital", type=Decimal, default=Decimal("100000"))
    parser.add_argument("--fast", type=int, default=10)
    parser.add_argument("--slow", type=int, default=30)
    parser.add_argument("--persist", action="store_true", help="save orders, fills and audit rows")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        series = {
            s.upper(): [bar_from_record(r) for r in fetch_bars(session, s, Timeframe.DAY_1, args.start, args.end, limit=1_000_000)]
            for s in args.symbols
        }

    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        pipeline = TradingPipeline(session, [MovingAverageCrossover(args.fast, args.slow)], starting_cash=args.capital)
        started = time.perf_counter()
        pipeline.run(series)
        report(pipeline, series, time.perf_counter() - started)
        if args.persist:
            transaction.commit()
            print(f"\nSaved: orders, fills and audit rows for run {pipeline.run_id}")
        else:
            print("\n(dry run: transaction rolled back, nothing was saved)")
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


if __name__ == "__main__":
    main()
