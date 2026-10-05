import argparse
import time

from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.engine.engine import SignalEngine
from app.engine.feed import HistoricalBarFeed, bar_from_record
from app.market_data.domain import Timeframe
from app.market_data.ingest import parse_utc
from app.market_data.repository import fetch_bars
from app.strategies.ma_crossover import MovingAverageCrossover


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strategies over stored bars and print signals")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--timeframe", type=Timeframe, default=Timeframe.DAY_1)
    parser.add_argument("--start", type=parse_utc, required=True)
    parser.add_argument("--end", type=parse_utc, required=True)
    parser.add_argument("--fast", type=int, default=10)
    parser.add_argument("--slow", type=int, default=30)
    args = parser.parse_args()

    with Session(get_engine()) as session:
        series = {
            symbol.upper(): [
                bar_from_record(record)
                for record in fetch_bars(session, symbol, args.timeframe, args.start, args.end, limit=1_000_000)
            ]
            for symbol in args.symbols
        }

    engine = SignalEngine([MovingAverageCrossover(args.fast, args.slow)])
    started = time.perf_counter()
    result = engine.run(HistoricalBarFeed(series))
    elapsed_ms = (time.perf_counter() - started) * 1000

    for s in result.signals:
        stop = s.stop_loss if s.stop_loss is not None else "-"
        target = s.take_profit if s.take_profit is not None else "-"
        print(f"{s.ts:%Y-%m-%d}  {s.symbol:<6} {s.action:<4} @ {s.price:>10.2f}  stop {stop:>8}  target {target:>8}  {s.reason}")
    print(f"\n{result.bars_processed} bars -> {len(result.signals)} signals in {elapsed_ms:.1f} ms")


if __name__ == "__main__":
    main()
