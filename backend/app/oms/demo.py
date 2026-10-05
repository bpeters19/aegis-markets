from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.engine.events import SignalAction, SignalEvent
from app.oms.manager import OrderManager, request_from_decision
from app.oms.states import OrderError
from app.risk.engine import RiskDecision, RiskStatus


def main() -> None:
    signal = SignalEvent(
        ts=datetime(2025, 2, 19, tzinfo=timezone.utc), symbol="NVDA", strategy_id="sma_cross_10_30",
        action=SignalAction.BUY, price=Decimal("138.87"),
        stop_loss=Decimal("131.92"), take_profit=Decimal("152.75"),
    )
    decision = RiskDecision(RiskStatus.APPROVED, signal, 72, Decimal("9998.64"), Decimal("499.68"))
    t = datetime(2025, 2, 20, 14, 30, tzinfo=timezone.utc)
    tick = timedelta(seconds=1)

    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        oms = OrderManager(session)
        request = request_from_decision(decision)

        order, created = oms.create(request, t)
        print(f"create   -> {order.client_order_id} (new order: {created})")
        _, created = oms.create(request, t + tick)
        print(f"retry    -> same order returned, new order: {created}")
        oms.submit(order.id, t + 2 * tick)
        oms.apply_fill(order.id, "demo-exec-1", 30, Decimal("138.90"), t + 3 * tick)
        _, applied = oms.apply_fill(order.id, "demo-exec-1", 30, Decimal("138.90"), t + 4 * tick)
        print(f"dup fill -> applied: {applied}")
        oms.apply_fill(order.id, "demo-exec-2", 42, Decimal("138.95"), t + 5 * tick)
        try:
            oms.cancel(order.id, t + 6 * tick, "too late")
        except OrderError as exc:
            print(f"cancel   -> refused: {exc}")

        print(f"\nfinal: {order.status}, {order.filled_quantity}/{order.quantity} @ avg {order.avg_fill_price:.4f}\n")
        print("audit trail:")
        for e in oms.events(order.id):
            print(f"  {e.occurred_at:%H:%M:%S}  {e.event:<10} {e.from_status or '-':>16} -> {e.to_status:<16} {e.detail}")
    finally:
        session.close()
        transaction.rollback()
        connection.close()
    print("\n(dry run: transaction rolled back, nothing was saved)")


if __name__ == "__main__":
    main()
