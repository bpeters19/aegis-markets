from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.execution.costs import CostModel
from app.execution.simulator import ExecutionSimulator, WorkingOrder
from app.market_data.domain import Bar, Timeframe
from app.oms.states import OrderSide, OrderType

DAY0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
DAY1 = DAY0 + timedelta(days=1)


def bar(o, h, l, c, ts=DAY1, volume=1_000_000):
    return Bar(
        symbol="TEST", timeframe=Timeframe.DAY_1, ts=ts,
        open=Decimal(str(o)), high=Decimal(str(h)), low=Decimal(str(l)), close=Decimal(str(c)),
        volume=Decimal(volume),
    )


def order(side, order_type, qty=10, submitted=DAY0, oid="o1", **kw):
    return WorkingOrder(oid, "TEST", side, order_type, qty, submitted, **kw)


def stop_sell(stop, oid="stop", qty=10, **kw):
    return order(OrderSide.SELL, OrderType.STOP, qty=qty, oid=oid, stop_price=Decimal(str(stop)), **kw)


def target_sell(limit, oid="target", qty=10, **kw):
    return order(OrderSide.SELL, OrderType.LIMIT, qty=qty, oid=oid, limit_price=Decimal(str(limit)), **kw)


sim = ExecutionSimulator()


def test_market_buy_fills_at_open_with_slippage_and_min_commission():
    fills = sim.execute(bar(100, 101, 99, 100), [order(OrderSide.BUY, OrderType.MARKET)]).fills
    assert len(fills) == 1
    assert fills[0].price == Decimal("100.05")
    assert fills[0].commission == Decimal("1.00")
    assert fills[0].reason == "market_at_open"


def test_market_sell_slippage_rounds_against_the_trader():
    fills = sim.execute(bar(100.03, 101, 99, 100), [order(OrderSide.SELL, OrderType.MARKET)]).fills
    assert fills[0].price == Decimal("99.97")


def test_order_cannot_fill_on_a_bar_that_started_before_it_was_submitted():
    late = order(OrderSide.BUY, OrderType.MARKET, submitted=DAY1 + timedelta(hours=1))
    with pytest.raises(ValueError):
        sim.execute(bar(100, 101, 99, 100), [late])


def test_stop_triggered_inside_the_bar_fills_at_stop_less_slippage():
    fills = sim.execute(bar(98, 99, 94, 96), [stop_sell(95)]).fills
    assert fills[0].price == Decimal("94.95")
    assert fills[0].reason == "stop_triggered"


def test_gap_through_stop_fills_at_the_open_not_the_stop():
    fills = sim.execute(bar(100, 102, 98, 101), [stop_sell("109.07")]).fills
    assert fills[0].price == Decimal("99.95")
    assert fills[0].reason == "stop_gapped"


def test_stop_not_triggered_when_low_stays_above_it():
    assert sim.execute(bar(98, 99, 96, 97), [stop_sell(95)]).fills == []


@pytest.mark.parametrize("o, h, l, c, price, reason", [
    (105, 111, 104, 109, "110", "limit_triggered"),
    (112, 113, 111, 112, "112", "limit_gapped"),
])
def test_take_profit_fills_at_limit_or_better_without_slippage(o, h, l, c, price, reason):
    fills = sim.execute(bar(o, h, l, c), [target_sell(110)]).fills
    assert fills[0].price == Decimal(price)
    assert fills[0].reason == reason


def test_oco_ambiguous_bar_assumes_stop_hit_first():
    result = sim.execute(bar(100, 111, 94, 105), [stop_sell(95, oco_group="b"), target_sell(110, oco_group="b")])
    assert [f.order_id for f in result.fills] == ["stop"]
    assert [c.order_id for c in result.cancels] == ["target"]


def test_oco_gap_up_through_target_takes_target():
    result = sim.execute(bar(112, 113, 94, 100), [stop_sell(95, oco_group="b"), target_sell(110, oco_group="b")])
    assert [f.order_id for f in result.fills] == ["target"]
    assert result.fills[0].price == Decimal("112")
    assert [c.order_id for c in result.cancels] == ["stop"]


def test_oco_sibling_cancelled_when_only_one_triggers():
    result = sim.execute(bar(100, 101, 94, 96), [stop_sell(95, oco_group="b"), target_sell(110, oco_group="b")])
    assert [f.order_id for f in result.fills] == ["stop"]
    assert [c.order_id for c in result.cancels] == ["target"]


def test_market_order_partially_fills_when_volume_is_thin():
    fills = sim.execute(bar(100, 101, 99, 100, volume=500), [order(OrderSide.BUY, OrderType.MARKET, qty=80)]).fills
    assert fills[0].quantity == 50


def test_commission_per_share_above_minimum():
    assert CostModel().commission(1000) == Decimal("5.00")


def test_bracket_placed_at_the_open_can_trigger_on_the_same_bar():
    child = stop_sell(95, submitted=DAY1)
    fills = sim.execute(bar(100, 101, 94, 96), [child]).fills
    assert fills[0].price == Decimal("94.95")
    assert fills[0].reason == "stop_triggered"
