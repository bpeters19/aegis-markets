import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.oms.models import FillRecord, OrderEventRecord, OrderRecord
from app.oms.states import OrderError, OrderSide, OrderStatus, OrderType, ensure_transition
from app.risk.engine import RiskDecision


class IdempotencyConflict(OrderError):
    pass


class OverfillError(OrderError):
    pass


@dataclass(frozen=True)
class OrderRequest:
    client_order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    requested_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    strategy_id: str = "manual"

    def __post_init__(self) -> None:
        if not 0 < len(self.client_order_id) <= 64:
            raise OrderError("client_order_id must be 1-64 characters")
        if self.quantity <= 0:
            raise OrderError("quantity must be positive")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise OrderError("limit orders need a limit_price")
        if self.order_type == OrderType.STOP and self.stop_price is None:
            raise OrderError("stop orders need a stop_price")
        if self.order_type == OrderType.MARKET and (self.limit_price or self.stop_price):
            raise OrderError("market orders cannot have a limit or stop price")


def request_from_decision(decision: RiskDecision) -> OrderRequest:
    """Turn an approved risk decision into an order request with a deterministic client ID,
    so replaying the same signal can never create a second order."""
    if not decision.approved:
        raise OrderError("only approved risk decisions can become orders")
    s = decision.signal
    return OrderRequest(
        client_order_id=f"{s.strategy_id}:{s.symbol}:{s.action}:{s.ts:%Y%m%dT%H%M%SZ}",
        symbol=s.symbol,
        side=OrderSide(s.action),
        quantity=decision.quantity,
        requested_price=s.price,
        stop_loss=s.stop_loss,
        take_profit=s.take_profit,
        strategy_id=s.strategy_id,
    )


IDENTITY_FIELDS = ("symbol", "side", "order_type", "quantity", "limit_price", "stop_price")


class OrderManager:
    """Owns order state. Every change is validated by the state machine and written to the
    audit log in the same transaction. Methods flush; the caller commits."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, request: OrderRequest, ts: datetime) -> tuple[OrderRecord, bool]:
        existing = self._by_client_id(request.client_order_id)
        if existing is not None:
            return self._same_or_conflict(existing, request), False

        order = OrderRecord(
            client_order_id=request.client_order_id,
            symbol=request.symbol.strip().upper(),
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            requested_price=request.requested_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            strategy_id=request.strategy_id,
            status=OrderStatus.PENDING,
            filled_quantity=0,
            created_at=ts,
        )
        try:
            with self.session.begin_nested():
                self.session.add(order)
                self.session.flush()
        except IntegrityError:
            existing = self._by_client_id(request.client_order_id)
            if existing is None:
                raise
            return self._same_or_conflict(existing, request), False

        self._audit(order, "CREATED", None, OrderStatus.PENDING, ts, {
            "side": str(request.side),
            "quantity": request.quantity,
            "order_type": str(request.order_type),
            "requested_price": str(request.requested_price) if request.requested_price is not None else None,
        })
        self.session.flush()
        return order, True

    def submit(self, order_id: uuid.UUID, ts: datetime) -> OrderRecord:
        return self._transition(order_id, OrderStatus.SUBMITTED, "SUBMITTED", ts)

    def cancel(self, order_id: uuid.UUID, ts: datetime, reason: str) -> OrderRecord:
        return self._transition(order_id, OrderStatus.CANCELLED, "CANCELLED", ts, {"reason": reason})

    def reject(self, order_id: uuid.UUID, ts: datetime, reason: str) -> OrderRecord:
        return self._transition(order_id, OrderStatus.REJECTED, "REJECTED", ts, {"reason": reason})

    def apply_fill(
        self,
        order_id: uuid.UUID,
        execution_id: str,
        quantity: int,
        price: Decimal,
        ts: datetime,
    ) -> tuple[OrderRecord, bool]:
        order = self._get(order_id)

        duplicate = self.session.scalar(select(FillRecord).where(FillRecord.execution_id == execution_id))
        if duplicate is not None:
            if duplicate.order_id != order.id:
                raise OrderError(f"execution {execution_id} belongs to a different order")
            return order, False

        if quantity <= 0 or price <= 0:
            raise OrderError("fill quantity and price must be positive")
        new_filled = order.filled_quantity + quantity
        if new_filled > order.quantity:
            raise OverfillError(f"fill of {quantity} would exceed order quantity {order.quantity}")

        previous = OrderStatus(order.status)
        target = OrderStatus.FILLED if new_filled == order.quantity else OrderStatus.PARTIALLY_FILLED
        ensure_transition(previous, target)

        self.session.add(FillRecord(
            order_id=order.id, execution_id=execution_id, quantity=quantity, price=price, filled_at=ts,
        ))
        self.session.flush()

        total_value = self.session.scalar(
            select(func.sum(FillRecord.quantity * FillRecord.price)).where(FillRecord.order_id == order.id)
        )
        order.filled_quantity = new_filled
        order.avg_fill_price = (total_value / new_filled).quantize(Decimal("0.000001"))
        order.status = target
        if target == OrderStatus.FILLED:
            order.filled_at = ts

        self._audit(order, "FILL", previous, target, ts, {
            "execution_id": execution_id,
            "quantity": quantity,
            "price": str(price),
            "filled_quantity": new_filled,
            "avg_fill_price": str(order.avg_fill_price),
        })
        self.session.flush()
        return order, True

    def events(self, order_id: uuid.UUID) -> list[OrderEventRecord]:
        stmt = select(OrderEventRecord).where(OrderEventRecord.order_id == order_id).order_by(OrderEventRecord.id)
        return list(self.session.scalars(stmt))

    def _transition(
        self,
        order_id: uuid.UUID,
        target: OrderStatus,
        event: str,
        ts: datetime,
        detail: dict[str, Any] | None = None,
    ) -> OrderRecord:
        order = self._get(order_id)
        previous = OrderStatus(order.status)
        ensure_transition(previous, target)
        order.status = target
        self._audit(order, event, previous, target, ts, detail or {})
        self.session.flush()
        return order

    def _audit(
        self,
        order: OrderRecord,
        event: str,
        previous: OrderStatus | None,
        target: OrderStatus,
        ts: datetime,
        detail: dict[str, Any],
    ) -> None:
        self.session.add(OrderEventRecord(
            order_id=order.id, event=event, from_status=previous, to_status=target,
            occurred_at=ts, detail=detail,
        ))

    def _get(self, order_id: uuid.UUID) -> OrderRecord:
        order = self.session.get(OrderRecord, order_id)
        if order is None:
            raise OrderError(f"unknown order {order_id}")
        return order

    def _by_client_id(self, client_order_id: str) -> OrderRecord | None:
        return self.session.scalar(select(OrderRecord).where(OrderRecord.client_order_id == client_order_id))

    @staticmethod
    def _same_or_conflict(existing: OrderRecord, request: OrderRequest) -> OrderRecord:
        for name in IDENTITY_FIELDS:
            if getattr(existing, name) != getattr(request, name):
                raise IdempotencyConflict(
                    f"client_order_id {request.client_order_id} already used with a different {name}"
                )
        return existing
