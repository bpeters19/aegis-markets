"""Daily paper-trading run: python -m app.paper.run [--account NAME] [--skip-ingest]

Run after 6 PM New York time to record that day. Earlier runs record only through the previous day."""
import argparse
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.backtest.run import load
from app.core.config import get_settings
from app.database.session import get_engine
from app.market_data.domain import Timeframe
from app.market_data.models import BarRecord
from app.market_data.providers.tiingo import TiingoProvider
from app.market_data.service import ingest_bars
from app.paper.accounts import STRATEGY_HYPOTHESES
from app.paper.ledger import DayState, find_drift, unrecorded_days
from app.paper.models import PaperAccount, PaperDay
from app.paper.replay import ReplayDay, replay
from app.research.config import config_hash
from app.research.evaluation import at
from app.research.fingerprint import data_hash, git_commit

NEW_YORK = ZoneInfo("America/New_York")
FINAL_HOUR = 18  # vendors publish final daily bars a while after the 4 PM close


def complete_through(now: datetime) -> date:
    local = now.astimezone(NEW_YORK)
    return local.date() if local.hour >= FINAL_HOUR else local.date() - timedelta(days=1)


def ingest_latest(session: Session, symbols: list[str], through: date) -> None:
    provider = TiingoProvider.from_settings(get_settings())
    for symbol in symbols:
        last = session.scalar(
            select(func.max(BarRecord.ts)).where(BarRecord.symbol == symbol, BarRecord.timeframe == "1Day")
        )
        begin = last - timedelta(days=7) if last else at(through) - timedelta(days=400)
        ingest_bars(session, provider, symbol, Timeframe.DAY_1, begin, at(through + timedelta(days=1)))


def describe(items: list[dict], kind: str) -> str:
    if not items:
        return "none"
    if kind == "fills":
        return ", ".join(f"{i['side']} {i['quantity']} {i['symbol']} @ {i['price']} ({i['role']})" for i in items)
    return ", ".join(f"{i['side']} {i['quantity']} {i['symbol']} ({i['role']}, {i['type']})" for i in items)


def report(account: PaperAccount, latest: ReplayDay, new_count: int) -> None:
    held = ", ".join(f"{s} {q}" for s, q in sorted(latest.positions.items())) or "none"
    print(f"\n{account.name} ({account.hypothesis_id}) through {latest.day}: {new_count} new day(s) recorded")
    print(f"  Equity ${latest.equity:,.2f} ({latest.equity / account.capital - 1:+.2%} since {account.start_date}) | "
          f"cash ${latest.cash:,.2f} | exposure {latest.exposure:.1%}")
    print(f"  Positions: {held}")
    print(f"  Fills on {latest.day}: {describe(latest.fills, 'fills')}")
    print(f"  Orders for the next session: {describe(latest.orders, 'orders')}")


def run_account(session: Session, account: PaperAccount, through: date, commit: str) -> bool:
    config = STRATEGY_HYPOTHESES[account.hypothesis_id]
    if config_hash(config) != account.config_hash:
        print(f"\n{account.name}: config changed since the account started ({account.config_hash}); not running.")
        return False
    if through < account.start_date:
        print(f"\n{account.name}: no complete trading day since the start date {account.start_date} yet.")
        return True

    series = load(list(config.universe), at(account.start_date) - timedelta(days=400), at(through + timedelta(days=1)))
    days = replay(config, account.start_date, account.capital, series, through)
    if not days:
        print(f"\n{account.name}: no trading days between {account.start_date} and {through} yet.")
        return True

    recorded = list(session.scalars(
        select(PaperDay).where(PaperDay.account_id == account.id).order_by(PaperDay.day)
    ))
    old = [DayState(r.day, r.equity, dict(r.positions)) for r in recorded]
    new = [DayState(d.day, d.equity, d.positions) for d in days]
    drift = find_drift(old, new)
    if drift:
        print(f"\n{account.name}: DRIFT DETECTED, nothing written.")
        for day, issue in drift:
            print(f"  {day}: {issue}")
        return False

    by_day = {d.day: d for d in days}
    fresh = [by_day[s.day] for s in unrecorded_days(old, new)]
    fingerprint = data_hash(series)
    for d in fresh:
        session.add(PaperDay(
            account_id=account.id, day=d.day, equity=d.equity, cash=d.cash, exposure=d.exposure,
            positions=d.positions, fills=d.fills, working_orders=d.orders,
            data_hash=fingerprint, code_commit=commit,
        ))
    session.commit()
    report(account, days[-1], len(fresh))
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the latest complete trading day for paper accounts")
    parser.add_argument("--account", help="run a single account by name")
    parser.add_argument("--skip-ingest", action="store_true", help="use bars already in the database")
    args = parser.parse_args()

    commit = git_commit()
    if commit.endswith("+dirty"):
        raise SystemExit("There are uncommitted changes. The ledger records which commit produced each day, so commit first.")

    through = complete_through(datetime.now(timezone.utc))
    print(f"Recording complete trading days through {through} (code {commit})")
    with Session(get_engine()) as session:
        query = select(PaperAccount).order_by(PaperAccount.id)
        if args.account:
            query = query.where(PaperAccount.name == args.account)
        accounts = list(session.scalars(query))
        if not accounts:
            raise SystemExit("No matching paper accounts.")

        if not args.skip_ingest:
            symbols = sorted({s for a in accounts for s in STRATEGY_HYPOTHESES[a.hypothesis_id].universe})
            print(f"Fetching latest bars for {len(symbols)} symbols ...", flush=True)
            ingest_latest(session, symbols, through)

        results = [run_account(session, account, through, commit) for account in accounts]
    if not all(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
