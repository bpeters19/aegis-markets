from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.market_data.domain import Bar, Timeframe
from app.oms.models import OrderRecord
from app.risk.limits import RiskLimits
from app.strategies.ma_crossover import MovingAverageCrossover
from app.trading.pipeline import TradingPipeline

pytestmark = pytest.mark.integration

BASE = datetime(2026, 1, 5, tzinfo=timezone.utc)
SETUP = [(c, c + 1, c - 1, c) for c in (10, 10, 10, 10, 13)]


@pytest.fixture
def session():
    connection = get_engine().connect()
    transaction = connection.begin()
    s = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        transaction.rollback()
        connection.close()


def bars(symbol, ohlc):
    return [
        Bar(symbol=symbol, timeframe=Timeframe.DAY_1, ts=BASE + timedelta(days=i),
            open=D(str(o)), high=D(str(h)), low=D(str(l)), close=D(str(c)), volume=D("1000000"))
        for i, (o, h, l, c) in enumerate(ohlc)
    ]


def run(session, series, **kwargs):
    return TradingPipeline(session, [MovingAverageCrossover(2, 3)], **kwargs).run(series)


def order_statuses(session, pipeline):
    rows = session.execute(
        select(OrderRecord.client_order_id, OrderRecord.status)
        .where(OrderRecord.client_order_id.like(f"{pipeline.run_id}:%"))
    ).all()
    return {(cid[-2:] if cid.endswith((":SL", ":TP")) else "ENTRY"): status for cid, status in rows}


def test_entry_then_same_day_stop_out(session):
    p = run(session, {"AAA": bars("AAA", SETUP + [(13, 13.5, 12, 12.5)])})

    [trade] = p.portfolio.trades
    assert trade.exit_reason == "stop_triggered"
    assert trade.quantity == 769
    assert trade.avg_entry == D("13.01")
    assert trade.avg_exit == D("12.34")
    assert trade.net_pnl == D("-522.93")
    assert p.portfolio.positions == {}
    assert p.portfolio.equity == D("99477.07")
    assert order_statuses(session, p) == {"ENTRY": "FILLED", "SL": "FILLED", "TP": "CANCELLED"}


def test_entry_then_take_profit(session):
    p = run(session, {"AAA": bars("AAA", SETUP + [(13, 14.5, 12.8, 14)])})

    [trade] = p.portfolio.trades
    assert trade.exit_reason == "limit_triggered"
    assert trade.avg_exit == D("14.30")
    assert trade.net_pnl == D("984.31")
    assert order_statuses(session, p) == {"ENTRY": "FILLED", "SL": "CANCELLED", "TP": "FILLED"}


def test_working_orders_count_toward_risk_limits(session):
    series = {"AAA": bars("AAA", SETUP), "BBB": bars("BBB", SETUP)}
    p = run(session, series, limits=RiskLimits(max_open_positions=1))

    assert p.counts["approved"] == 1
    assert p.counts["rejected"] == 1
    [rejected] = [d for d in p.decisions if not d.approved]
    assert rejected.signal.symbol == "BBB"
    assert any("max open positions" in r for r in rejected.reasons)


def test_entry_cancelled_when_open_gaps_below_stop(session):
    p = run(session, {"AAA": bars("AAA", SETUP + [(12, 12.5, 11.5, 12)])})

    assert p.portfolio.trades == []
    assert p.portfolio.positions == {}
    assert p.counts["gap_cancels"] == 1
    assert order_statuses(session, p) == {"ENTRY": "CANCELLED"}


def test_signals_before_trade_from_are_ignored(session):
    p = TradingPipeline(
        session, [MovingAverageCrossover(2, 3)], trade_from=BASE + timedelta(days=10)
    ).run({"AAA": bars("AAA", SETUP)})
    assert p.counts["warmup_signals"] == 1
    assert p.counts["orders"] == 0
