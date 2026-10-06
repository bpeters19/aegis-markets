import argparse
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.engine.feed import bar_from_record
from app.execution.costs import CostModel
from app.execution.simulator import ExecutionSimulator, SimFill, WorkingOrder, bar_end
from app.market_data.domain import Timeframe
from app.market_data.ingest import parse_utc
from app.market_data.repository import fetch_bars
from app.oms.states import OrderSide, OrderType


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay one bracketed trade with realistic execution")
    parser.add_argument("--symbol", default="AMD")
    parser.add_argument("--signal-date", type=parse_utc, default=parse_utc("2025-03-25"))
    parser.add_argument("--end", type=parse_utc, default=parse_utc("2026-01-01"))
    parser.add_argument("--quantity", type=int, default=84)
    parser.add_argument("--stop", type=Decimal, default=Decimal("109.07"))
    parser.add_argument("--target", type=Decimal, default=Decimal("126.29"))
    args = parser.parse_args()

    with Session(get_engine()) as session:
        records = fetch_bars(session, args.symbol, Timeframe.DAY_1, args.signal_date, args.end, limit=100_000)
        bars = [bar_from_record(r) for r in records]
    if not bars or bars[0].ts.date() != args.signal_date.date():
        raise SystemExit(f"No {args.symbol} bar on {args.signal_date:%Y-%m-%d}; ingest data first.")

    sim = ExecutionSimulator(CostModel())
    signal_bar = bars[0]
    symbol, qty = signal_bar.symbol, args.quantity
    planned_risk = (signal_bar.close - args.stop) * qty
    print(f"Signal   {signal_bar.ts:%Y-%m-%d}  BUY {qty} {symbol} on the close at ${signal_bar.close:.2f}  "
          f"stop ${args.stop}  target ${args.target}  planned risk ${planned_risk:,.2f}")

    working = [WorkingOrder("entry", symbol, OrderSide.BUY, OrderType.MARKET, qty, bar_end(signal_bar))]
    entry: SimFill | None = None
    commissions = Decimal(0)

    for bar in bars[1:]:
        result = sim.execute(bar, working)
        if entry is None:
            if not result.fills:
                continue
            entry = result.fills[0]
            commissions += entry.commission
            print(f"Entry    {entry.ts:%Y-%m-%d}  bought {entry.quantity} @ ${entry.price}  "
                  f"(open ${bar.open:.2f} + slippage, commission ${entry.commission})")
            working = [
                WorkingOrder("stop", symbol, OrderSide.SELL, OrderType.STOP, entry.quantity, entry.ts,
                             stop_price=args.stop, oco_group="bracket"),
                WorkingOrder("target", symbol, OrderSide.SELL, OrderType.LIMIT, entry.quantity, entry.ts,
                             limit_price=args.target, oco_group="bracket"),
            ]
            result = sim.execute(bar, working)

        if result.fills:
            exit_ = result.fills[0]
            commissions += exit_.commission
            print(f"Exit     {exit_.ts:%Y-%m-%d}  {exit_.order_id.upper()} sold {exit_.quantity} @ ${exit_.price}  "
                  f"[{exit_.reason}]  bar O/H/L/C {bar.open:.2f}/{bar.high:.2f}/{bar.low:.2f}/{bar.close:.2f}")
            for cancel in result.cancels:
                print(f"         {cancel.order_id} cancelled ({cancel.reason})")
            gross = (exit_.price - entry.price) * exit_.quantity
            net = gross - commissions
            print(f"\nGross P&L ${gross:,.2f}   commissions ${commissions:.2f}   net P&L ${net:,.2f}")
            print(f"Planned risk ${planned_risk:,.2f}   realized / planned = {abs(net) / planned_risk:.2f}x")
            return

    print("Position still open at the end of the data.")


if __name__ == "__main__":
    main()
