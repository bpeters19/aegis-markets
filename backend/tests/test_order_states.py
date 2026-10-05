from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.engine.events import SignalAction, SignalEvent
from app.oms.manager import OrderRequest, request_from_decision
from app.oms.states import (
    TERMINAL, InvalidTransition, OrderError, OrderSide, OrderStatus as S, OrderType, ensure_transition,
)
from app.risk.engine import RiskDecision, RiskStatus


def test_happy_path_transitions_are_legal():
    path = [S.PENDING, S.SUBMITTED, S.PARTIALLY_FILLED, S.PARTIALLY_FILLED, S.FILLED]
    for current, target in zip(path, path[1:]):
        ensure_transition(current, target)


@pytest.mark.parametrize("current, target", [
    (S.FILLED, S.CANCELLED),
    (S.PENDING, S.FILLED),
    (S.CANCELLED, S.SUBMITTED),
    (S.REJECTED, S.SUBMITTED),
    (S.PARTIALLY_FILLED, S.REJECTED),
])
def test_illegal_transitions_raise(current, target):
    with pytest.raises(InvalidTransition):
        ensure_transition(current, target)


def test_terminal_states():
    assert TERMINAL == {S.FILLED, S.CANCELLED, S.REJECTED}


def test_order_request_validation():
    with pytest.raises(OrderError):
        OrderRequest("id-1", "NVDA", OrderSide.BUY, 0)
    with pytest.raises(OrderError):
        OrderRequest("id-2", "NVDA", OrderSide.BUY, 10, order_type=OrderType.LIMIT)
    with pytest.raises(OrderError):
        OrderRequest("id-3", "NVDA", OrderSide.BUY, 10, limit_price=Decimal("100"))


def make_decision(status=RiskStatus.APPROVED):
    signal = SignalEvent(
        ts=datetime(2025, 2, 19, tzinfo=timezone.utc), symbol="NVDA", strategy_id="sma_cross_10_30",
        action=SignalAction.BUY, price=Decimal("138.87"),
        stop_loss=Decimal("131.92"), take_profit=Decimal("152.75"),
    )
    return RiskDecision(status, signal, 72, Decimal("9998.64"), Decimal("499.68"))


def test_request_from_decision_uses_deterministic_client_id():
    first = request_from_decision(make_decision())
    second = request_from_decision(make_decision())
    assert first.client_order_id == second.client_order_id == "sma_cross_10_30:NVDA:BUY:20250219T000000Z"
    assert first.quantity == 72
    assert first.side == OrderSide.BUY
    assert first.stop_loss == Decimal("131.92")


def test_rejected_decision_cannot_become_an_order():
    with pytest.raises(OrderError):
        request_from_decision(make_decision(RiskStatus.REJECTED))
