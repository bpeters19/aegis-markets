import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.oms.manager import IdempotencyConflict, OrderManager, OrderRequest, OverfillError
from app.oms.models import OrderRecord
from app.oms.states import InvalidTransition, OrderSide, OrderStatus

pytestmark = pytest.mark.integration

T0 = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)


@pytest.fixture
def session():
    """Everything a test writes is rolled back, including audit rows the trigger won't let us delete."""
    connection = get_engine().connect()
    transaction = connection.begin()
    s = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        transaction.rollback()
        connection.close()


def new_request(quantity=100):
    return OrderRequest(
        client_order_id=f"test-{uuid.uuid4()}", symbol="NVDA", side=OrderSide.BUY,
        quantity=quantity, requested_price=Decimal("100"),
    )


def exec_id():
    return f"exec-{uuid.uuid4()}"


def test_full_lifecycle_with_partial_fills(session):
    oms = OrderManager(session)
    order, created = oms.create(new_request(), T0)
    oms.submit(order.id, T0)
    oms.apply_fill(order.id, exec_id(), 40, Decimal("100"), T0)
    assert order.status == OrderStatus.PARTIALLY_FILLED
    oms.apply_fill(order.id, exec_id(), 60, Decimal("101"), T0)

    assert created
    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 100
    assert order.avg_fill_price == Decimal("100.6")
    assert order.filled_at == T0
    trail = [(e.event, e.from_status, e.to_status) for e in oms.events(order.id)]
    assert trail == [
        ("CREATED", None, "PENDING"),
        ("SUBMITTED", "PENDING", "SUBMITTED"),
        ("FILL", "SUBMITTED", "PARTIALLY_FILLED"),
        ("FILL", "PARTIALLY_FILLED", "FILLED"),
    ]


def test_create_is_idempotent(session):
    oms = OrderManager(session)
    request = new_request()
    first, created_first = oms.create(request, T0)
    second, created_second = oms.create(request, T0)

    assert created_first and not created_second
    assert first.id == second.id
    count = session.scalar(
        select(func.count()).select_from(OrderRecord).where(OrderRecord.client_order_id == request.client_order_id)
    )
    assert count == 1
    assert [e.event for e in oms.events(first.id)] == ["CREATED"]


def test_reused_client_id_with_different_details_conflicts(session):
    oms = OrderManager(session)
    request = new_request()
    oms.create(request, T0)
    with pytest.raises(IdempotencyConflict):
        oms.create(replace(request, quantity=200), T0)


def test_duplicate_execution_report_is_ignored(session):
    oms = OrderManager(session)
    order, _ = oms.create(new_request(), T0)
    oms.submit(order.id, T0)
    execution = exec_id()
    _, applied_first = oms.apply_fill(order.id, execution, 40, Decimal("100"), T0)
    _, applied_second = oms.apply_fill(order.id, execution, 40, Decimal("100"), T0)

    assert applied_first and not applied_second
    assert order.filled_quantity == 40


def test_overfill_rejected(session):
    oms = OrderManager(session)
    order, _ = oms.create(new_request(quantity=100), T0)
    oms.submit(order.id, T0)
    with pytest.raises(OverfillError):
        oms.apply_fill(order.id, exec_id(), 150, Decimal("100"), T0)
    assert order.status == OrderStatus.SUBMITTED
    assert order.filled_quantity == 0


def test_cancel_partial_fill_keeps_filled_shares_and_is_final(session):
    oms = OrderManager(session)
    order, _ = oms.create(new_request(), T0)
    oms.submit(order.id, T0)
    oms.apply_fill(order.id, exec_id(), 40, Decimal("100"), T0)
    oms.cancel(order.id, T0, "end of day")

    assert order.status == OrderStatus.CANCELLED
    assert order.filled_quantity == 40
    with pytest.raises(InvalidTransition):
        oms.cancel(order.id, T0, "again")


def test_audit_log_is_append_only(session):
    oms = OrderManager(session)
    order, _ = oms.create(new_request(), T0)

    for sql in (
        "UPDATE order_events SET event = 'TAMPERED' WHERE order_id = :id",
        "DELETE FROM order_events WHERE order_id = :id",
    ):
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(text(sql), {"id": order.id})

    assert [e.event for e in oms.events(order.id)] == ["CREATED"]
