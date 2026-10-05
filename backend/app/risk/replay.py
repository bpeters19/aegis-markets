import argparse
from collections import Counter
from dataclasses import replace
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.engine.engine import SignalEngine
from app.engine.events import BarEvent, SignalAction, SignalEvent
from app.engine.feed import HistoricalBarFeed, bar_from_record
from app.market_data.domain import Timeframe
from app.market_data.ingest import parse_utc
from app.market_data.repository import fetch_bars
from app.portfolio.snapshot import PortfolioSnapshot, Position
from app.risk.engine import RiskDecision, RiskEngine
from app.strategies.ma_crossover import MovingAverageCrossover


class NaiveBook:
    """DEMO ONLY: fills approved orders instantly at the signal price, ignores stops and
    targets. Replaced by the execution simulator and portfolio engine in Week 5."""

    def __init__(self, cash: Decimal) -> None:
        self.cash = cash
        self.positions: dict[str, Position] = {}
        self.start_of_day_equity = cash
        self._day: date | None = None

    def snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(self.cash, dict(self.positions), self.start_of_day_equity)

    def on_bar(self, event: BarEvent) -> None:
        bar = event.bar
        if bar.ts.date() != self._day:
            self._day = bar.ts.date()
            self.start_of_day_equity = self.snapshot().equity
        if bar.symbol in self.positions:
            self.positions[bar.symbol] = replace(self.positions[bar.symbol], market_price=bar.close)

    def fill(self, decision: RiskDecision) -> None:
        signal = decision.signal
        if signal.action == SignalAction.BUY:
            self.cash -= decision.notional
            self.positions[signal.symbol] = Position(signal.symbol, decision.quantity, signal.price, signal.price)
        else:
            self.cash += decision.notional
            del self.positions[signal.symbol]


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay signals through the risk engine")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--start", type=parse_utc, required=True)
    parser.add_argument("--end", type=parse_utc, required=True)
    parser.add_argument("--capital", type=Decimal, default=Decimal("100000"))
    parser.add_argument("--fast", type=int, default=10)
    parser.add_argument("--slow", type=int, default=30)
    args = parser.parse_args()

    with Session(get_engine()) as session:
        series = {
            s.upper(): [bar_from_record(r) for r in fetch_bars(session, s, Timeframe.DAY_1, args.start, args.end, limit=1_000_000)]
            for s in args.symbols
        }

    risk = RiskEngine()
    book = NaiveBook(args.capital)
    engine = SignalEngine([MovingAverageCrossover(args.fast, args.slow)])
    engine.bus.subscribe(BarEvent, book.on_bar)
    counts: Counter[str] = Counter()

    def on_signal(signal: SignalEvent) -> None:
        decision = risk.evaluate(signal, book.snapshot())
        counts[decision.status] += 1
        if decision.approved:
            book.fill(decision)
            detail = f"{decision.quantity:>5} sh  ${decision.notional:>10,.0f}"
            if signal.action == SignalAction.BUY:
                detail += f"  risk ${decision.risk_amount:,.0f}  ({decision.notes[0]})"
        else:
            detail = "; ".join(decision.reasons)
        print(f"{signal.ts:%Y-%m-%d}  {signal.symbol:<6} {signal.action:<4}  {decision.status:<8}  {detail}")

    engine.bus.subscribe(SignalEvent, on_signal)
    engine.run(HistoricalBarFeed(series))

    print(f"\n{counts['APPROVED']} approved, {counts['REJECTED']} rejected")
    print(f"Open at end: {', '.join(sorted(book.positions)) or 'none'}")


if __name__ == "__main__":
    main()
