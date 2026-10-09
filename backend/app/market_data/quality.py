"""Data quality report: compares every symbol's bars against a reference trading calendar."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.market_data.domain import Timeframe
from app.market_data.repository import fetch_bars
from app.market_data.universes import UNIVERSES

EARLIEST = datetime(1990, 1, 1, tzinfo=timezone.utc)
LATEST = datetime(2100, 1, 1, tzinfo=timezone.utc)
JUMP_THRESHOLD = Decimal("0.20")


def main() -> None:
    parser = argparse.ArgumentParser(description="Report data gaps and suspicious moves per symbol")
    parser.add_argument("--universe", choices=UNIVERSES, default="etf_core")
    parser.add_argument("--calendar", default="SPY", help="symbol whose dates define the trading calendar")
    args = parser.parse_args()

    symbols = UNIVERSES[args.universe]
    with Session(get_engine()) as session:
        bars = {s: fetch_bars(session, s, Timeframe.DAY_1, EARLIEST, LATEST, limit=10_000_000) for s in symbols}
        calendar_bars = bars.get(args.calendar) or fetch_bars(
            session, args.calendar, Timeframe.DAY_1, EARLIEST, LATEST, limit=10_000_000
        )

    calendar = {b.ts.date() for b in calendar_bars}
    print(f"Calendar: {args.calendar}, {len(calendar)} trading days\n")
    print(f"{'symbol':<7}{'bars':>6}  {'first':<11}{'last':<11}{'missing':>8}{'extra':>7}  largest daily move")

    problems = 0
    for symbol, rows in bars.items():
        if not rows:
            print(f"{symbol:<7}{'0':>6}  NO DATA")
            problems += 1
            continue
        days = [r.ts.date() for r in rows]
        expected = {d for d in calendar if days[0] <= d <= days[-1]}
        missing = len(expected - set(days))
        extra = len(set(days) - calendar)

        jump, jump_day = Decimal(0), days[0]
        for prev, cur in zip(rows, rows[1:]):
            move = abs(cur.close / prev.close - 1)
            if move > jump:
                jump, jump_day = move, cur.ts.date()

        flags = []
        if missing:
            flags.append("GAPS")
        if extra:
            flags.append("OFF-CALENDAR")
        if jump > JUMP_THRESHOLD:
            flags.append("REVIEW JUMP")
        problems += bool(flags)
        print(f"{symbol:<7}{len(rows):>6}  {days[0]!s:<11}{days[-1]!s:<11}{missing:>8}{extra:>7}  "
              f"{jump:.1%} on {jump_day}  {' '.join(flags)}")

    print(f"\n{problems} symbol(s) flagged. A flagged jump is not automatically wrong (markets do move); "
          f"check it against the news before trusting or excluding it.")


if __name__ == "__main__":
    main()
