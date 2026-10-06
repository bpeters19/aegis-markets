from datetime import datetime, timezone
from decimal import Decimal as D

import pytest

from app.oms.states import OrderSide
from app.portfolio.engine import Portfolio
from tests.factories import make_bar

T = datetime(2026, 1, 2, tzinfo=timezone.utc)
BUY, SELL = OrderSide.BUY, OrderSide.SELL


def test_round_trip_records_trade_and_updates_cash():
    pf = Portfolio(D("10000"))
    pf.apply_fill("AAA", BUY, 10, D("100"), D("1"), T)
    trade = pf.apply_fill("AAA", SELL, 10, D("110"), D("1"), T, "limit_triggered")
    assert pf.cash == D("10098")
    assert pf.realized_pnl == D("100")
    assert trade.net_pnl == D("98")
    assert trade.exit_reason == "limit_triggered"
    assert pf.positions == {}
    pf.check_accounting()


def test_average_cost_and_partial_sell():
    pf = Portfolio(D("10000"))
    pf.apply_fill("AAA", BUY, 10, D("100"), D("0"), T)
    pf.apply_fill("AAA", BUY, 10, D("110"), D("0"), T)
    assert pf.positions["AAA"].avg_cost == D("105")
    pf.apply_fill("AAA", SELL, 5, D("120"), D("0"), T)
    assert pf.realized_pnl == D("75")
    assert pf.positions["AAA"].quantity == 15
    assert pf.positions["AAA"].avg_cost == D("105")
    assert pf.trades == []
    pf.check_accounting()


def test_cannot_sell_more_than_held_and_state_is_unchanged():
    pf = Portfolio(D("10000"))
    pf.apply_fill("AAA", BUY, 10, D("100"), D("0"), T)
    with pytest.raises(ValueError):
        pf.apply_fill("AAA", SELL, 11, D("100"), D("1"), T)
    assert pf.positions["AAA"].quantity == 10
    assert pf.cash == D("9000")


def test_mark_to_market_keeps_the_books_balanced():
    pf = Portfolio(D("10000"))
    pf.apply_fill("TEST", BUY, 10, D("100"), D("1"), T)
    pf.mark(make_bar(120))
    assert pf.unrealized_pnl == D("200")
    assert pf.equity == D("10199")
    pf.check_accounting()


def test_snapshot_counts_pending_buys_and_reserves_cash():
    pf = Portfolio(D("10000"))
    snap = pf.snapshot([("AAA", 10, D("100"))])
    assert snap.positions["AAA"].quantity == 10
    assert snap.cash == D("9000")
    assert snap.equity == D("10000")
    assert pf.positions == {}


def test_equity_curve_and_start_of_day_equity():
    pf = Portfolio(D("10000"))
    pf.start_bar(make_bar(100, day=0))
    pf.apply_fill("TEST", BUY, 10, D("100"), D("0"), T)
    pf.mark(make_bar(110, day=0))
    pf.start_bar(make_bar(110, day=1))
    assert pf.start_of_day_equity == D("10100")
    pf.close_day()
    assert [equity for _, equity in pf.equity_curve] == [D("10100"), D("10100")]


def test_idle_cash_earns_interest_and_books_still_balance():
    pf = Portfolio(D("10000"), cash_rate=D("0.0252"))
    pf.start_bar(make_bar(100, day=0))
    pf.close_day()
    assert pf.interest == D("1")
    assert pf.equity == D("10001")
    pf.check_accounting()
