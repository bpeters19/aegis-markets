import uuid
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.engine.bus import EventBus
from app.engine.engine import SignalEngine
from app.engine.events import BarEvent, SignalAction, SignalEvent
from app.engine.feed import HistoricalBarFeed
from app.execution.costs import CostModel
from app.execution.simulator import ExecutionSimulator, SimFill, WorkingOrder, bar_end
from app.market_data.domain import Bar
from app.oms.manager import OrderManager, OrderRequest, request_from_decision
from app.oms.models import FillRecord, OrderRecord
from app.oms.states import OrderSide, OrderType
from app.portfolio.engine import Portfolio
from app.risk.engine import RiskDecision, RiskEngine
from app.risk.limits import RiskLimits
from app.strategies.base import Strategy


class ReconciliationError(RuntimeError):
    pass


class TradingPipeline:
    """Strategy -> risk -> OMS -> execution simulator -> portfolio, driven by the event bus.

    For each bar, handlers run in subscription order:
      1. working orders execute against the bar (at the open or intrabar)
      2. bar history updates and strategies run (signals are queued)
      3. positions are marked to the close
      4. queued signals go through risk; approved ones become orders for the next bar
    """

    def __init__(
        self,
        session: Session,
        strategies: Sequence[Strategy],
        starting_cash: Decimal = Decimal("100000"),
        limits: RiskLimits | None = None,
        costs: CostModel | None = None,
        run_id: str | None = None,
    ) -> None:
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.bus = EventBus()
        self.bus.subscribe(BarEvent, self._execute_working_orders)
        self.signals = SignalEngine(strategies, bus=self.bus)
        self.bus.subscribe(BarEvent, self._mark_to_close)
        self.bus.subscribe(SignalEvent, self._on_signal)

        self.risk = RiskEngine(limits)
        self.oms = OrderManager(session)
        self.simulator = ExecutionSimulator(costs)
        self.portfolio = Portfolio(starting_cash)

        self.working: dict[str, WorkingOrder] = {}
        self.brackets: dict[str, tuple[Decimal | None, Decimal | None]] = {}
        self.last_bar: dict[str, Bar] = {}
        self.decisions: list[RiskDecision] = []
        self.counts: Counter[str] = Counter()
        self.bars_processed = 0

    def run(self, series: Mapping[str, Sequence[Bar]]) -> "TradingPipeline":
        result = self.signals.run(HistoricalBarFeed(series))
        self.bars_processed = result.bars_processed
        self.portfolio.close_day()
        self.portfolio.check_accounting()
        self.reconcile()
        return self

    def _execute_working_orders(self, event: BarEvent) -> None:
        bar = event.bar
        self.portfolio.start_bar(bar)
        self.last_bar[bar.symbol] = bar
        self._cancel_gapped_entries(bar)
        self._execute(bar, [o for o in self.working.values() if o.symbol == bar.symbol])

    def _cancel_gapped_entries(self, bar: Bar) -> None:
        """If the open has already gapped through an entry's stop or target, the setup the
        strategy saw no longer exists: cancel the entry instead of buying and exiting at once."""
        for order_id, order in list(self.working.items()):
            if order.symbol != bar.symbol or order_id not in self.brackets:
                continue
            stop_loss, take_profit = self.brackets[order_id]
            through_stop = stop_loss is not None and bar.open <= stop_loss
            through_target = take_profit is not None and bar.open >= take_profit
            if through_stop or through_target:
                del self.brackets[order_id]
                self._cancel(order_id, bar.ts, "open gapped through bracket level; setup invalidated")
                self.counts["gap_cancels"] += 1

    def _mark_to_close(self, event: BarEvent) -> None:
        self.portfolio.mark(event.bar)

    def _execute(self, bar: Bar, orders: list[WorkingOrder]) -> None:
        if not orders:
            return
        result = self.simulator.execute(bar, orders)
        children: list[WorkingOrder] = []
        for fill in result.fills:
            children.extend(self._handle_fill(fill))
        for cancel in result.cancels:
            self._cancel(cancel.order_id, bar.ts, cancel.reason)
        if children:
            self._execute(bar, children)

    def _handle_fill(self, fill: SimFill) -> list[WorkingOrder]:
        record, applied = self.oms.apply_fill(
            uuid.UUID(fill.order_id), fill.execution_id, fill.quantity, fill.price, fill.ts
        )
        if not applied:
            return []
        self.counts["fills"] += 1
        self.portfolio.apply_fill(
            fill.symbol, fill.side, fill.quantity, fill.price, fill.commission, fill.ts, fill.reason
        )

        order = self.working[fill.order_id]
        if fill.quantity < order.remaining:
            self.working[fill.order_id] = replace(order, remaining=order.remaining - fill.quantity)
            return []
        del self.working[fill.order_id]

        if fill.side == OrderSide.SELL and fill.symbol not in self.portfolio.positions:
            for other_id, other in list(self.working.items()):
                if other.symbol == fill.symbol and other.side == OrderSide.SELL:
                    self._cancel(other_id, fill.ts, "position closed")
            return []

        stop_loss, take_profit = self.brackets.pop(fill.order_id, (None, None))
        children = []
        if stop_loss is not None:
            children.append(self._submit(OrderRequest(
                client_order_id=f"{record.client_order_id}:SL", symbol=record.symbol, side=OrderSide.SELL,
                quantity=record.quantity, order_type=OrderType.STOP, stop_price=stop_loss,
                strategy_id=record.strategy_id,
            ), fill.ts, oco_group=fill.order_id))
        if take_profit is not None:
            children.append(self._submit(OrderRequest(
                client_order_id=f"{record.client_order_id}:TP", symbol=record.symbol, side=OrderSide.SELL,
                quantity=record.quantity, order_type=OrderType.LIMIT, limit_price=take_profit,
                strategy_id=record.strategy_id,
            ), fill.ts, oco_group=fill.order_id))
        return children

    def _on_signal(self, signal: SignalEvent) -> None:
        self.counts["signals"] += 1
        pending_buys = [
            (o.symbol, o.remaining, self.last_bar[o.symbol].close)
            for o in self.working.values()
            if o.side == OrderSide.BUY and o.oco_group is None
        ]
        decision = self.risk.evaluate(signal, self.portfolio.snapshot(pending_buys))
        self.decisions.append(decision)
        if not decision.approved:
            self.counts["rejected"] += 1
            return
        self.counts["approved"] += 1

        submitted_at = bar_end(self.last_bar[signal.symbol])
        if signal.action == SignalAction.SELL:
            for other_id, other in list(self.working.items()):
                if other.symbol == signal.symbol and other.side == OrderSide.SELL:
                    self._cancel(other_id, submitted_at, "replaced by strategy exit")

        request = request_from_decision(decision)
        request = replace(request, client_order_id=f"{self.run_id}:{request.client_order_id}")
        order = self._submit(request, submitted_at)
        if signal.action == SignalAction.BUY:
            self.brackets[order.order_id] = (signal.stop_loss, signal.take_profit)

    def _submit(self, request: OrderRequest, ts: datetime, oco_group: str | None = None) -> WorkingOrder:
        record, created = self.oms.create(request, ts)
        if not created:
            raise RuntimeError(f"client order id {request.client_order_id} was already used")
        self.oms.submit(record.id, ts)
        order = WorkingOrder(
            order_id=str(record.id), symbol=record.symbol, side=OrderSide(record.side),
            order_type=OrderType(record.order_type), remaining=record.quantity, submitted_at=ts,
            limit_price=record.limit_price, stop_price=record.stop_price, oco_group=oco_group,
        )
        self.working[order.order_id] = order
        self.counts["orders"] += 1
        return order

    def _cancel(self, order_id: str, ts: datetime, reason: str) -> None:
        if self.working.pop(order_id, None) is None:
            return
        self.oms.cancel(uuid.UUID(order_id), ts, reason)
        self.counts["cancels"] += 1

    def reconcile(self) -> None:
        """Portfolio positions must equal the net of all OMS fills for this run."""
        stmt = (
            select(OrderRecord.symbol, OrderRecord.side, func.sum(FillRecord.quantity))
            .join(FillRecord, FillRecord.order_id == OrderRecord.id)
            .where(OrderRecord.client_order_id.like(f"{self.run_id}:%"))
            .group_by(OrderRecord.symbol, OrderRecord.side)
        )
        from_oms: dict[str, int] = defaultdict(int)
        for symbol, side, quantity in self.oms.session.execute(stmt):
            from_oms[symbol] += quantity if side == OrderSide.BUY else -quantity
        held = {s: p.quantity for s, p in self.portfolio.positions.items()}
        breaks = {
            s: {"oms": from_oms.get(s, 0), "portfolio": held.get(s, 0)}
            for s in set(from_oms) | set(held)
            if from_oms.get(s, 0) != held.get(s, 0)
        }
        if breaks:
            raise ReconciliationError(f"position breaks between OMS and portfolio: {breaks}")
