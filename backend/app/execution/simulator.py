from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from app.execution.costs import CostModel
from app.market_data.domain import Bar, Timeframe
from app.oms.states import OrderSide, OrderType

BAR_DURATION = {
    Timeframe.MINUTE_1: timedelta(minutes=1),
    Timeframe.MINUTE_5: timedelta(minutes=5),
    Timeframe.MINUTE_15: timedelta(minutes=15),
    Timeframe.HOUR_1: timedelta(hours=1),
    Timeframe.DAY_1: timedelta(days=1),
}


def bar_end(bar: Bar) -> datetime:
    """When a bar is complete. Orders generated from a bar are submitted at this time."""
    return bar.ts + BAR_DURATION[bar.timeframe]


@dataclass(frozen=True, slots=True)
class WorkingOrder:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    remaining: int
    submitted_at: datetime
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    oco_group: str | None = None


@dataclass(frozen=True, slots=True)
class SimFill:
    order_id: str
    execution_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: Decimal
    commission: Decimal
    ts: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class SimCancel:
    order_id: str
    reason: str


@dataclass
class BarExecution:
    fills: list[SimFill] = field(default_factory=list)
    cancels: list[SimCancel] = field(default_factory=list)


class ExecutionSimulator:
    """Turns working orders into fills for one bar. Stateless and deterministic.

    Rules:
    - An order can only execute on bars that start at or after its submission time.
    - Market orders fill at the open plus slippage, capped by a share of bar volume.
    - Stops fill at the open if the bar gaps through them, otherwise at the stop, plus slippage.
    - Limits fill at the limit or better (the open, on a favorable gap), with no slippage.
    - OCO siblings: one fill cancels the rest. If both could trigger inside one bar,
      the stop is assumed to have happened first unless the open gapped through one.
    """

    def __init__(self, costs: CostModel | None = None) -> None:
        self.costs = costs or CostModel()

    def execute(self, bar: Bar, orders: Sequence[WorkingOrder]) -> BarExecution:
        result = BarExecution()
        oco_members: dict[str, list[WorkingOrder]] = defaultdict(list)
        oco_hits: dict[str, list[tuple[WorkingOrder, Decimal, str]]] = defaultdict(list)

        for order in orders:
            if order.symbol != bar.symbol:
                raise ValueError(f"order {order.order_id} is for {order.symbol}, bar is {bar.symbol}")
            if order.submitted_at > bar.ts:
                raise ValueError(
                    f"order {order.order_id} submitted at {order.submitted_at} cannot fill on a bar "
                    f"that started at {bar.ts}"
                )
            if order.oco_group:
                oco_members[order.oco_group].append(order)

        for order in orders:
            if order.remaining <= 0:
                continue
            hit = self._trigger(order, bar)
            if hit is None:
                continue
            price, reason = hit
            if order.oco_group:
                oco_hits[order.oco_group].append((order, price, reason))
            else:
                self._fill(result, order, bar, price, reason)

        for group, hits in oco_hits.items():
            winner, price, reason = min(hits, key=self._oco_priority)
            if self._fill(result, winner, bar, price, reason):
                for sibling in oco_members[group]:
                    if sibling.order_id != winner.order_id:
                        result.cancels.append(SimCancel(sibling.order_id, f"OCO: {winner.order_id} filled"))
        return result

    @staticmethod
    def _trigger(order: WorkingOrder, bar: Bar) -> tuple[Decimal, str] | None:
        o, h, l = bar.open, bar.high, bar.low
        sell = order.side == OrderSide.SELL

        if order.order_type == OrderType.MARKET:
            return o, "market_at_open"

        if order.order_type == OrderType.STOP:
            stop = order.stop_price
            if sell:
                if o <= stop:
                    return o, "stop_gapped"
                if l <= stop:
                    return stop, "stop_triggered"
            else:
                if o >= stop:
                    return o, "stop_gapped"
                if h >= stop:
                    return stop, "stop_triggered"
            return None

        limit = order.limit_price
        if sell:
            if o >= limit:
                return o, "limit_gapped"
            if h >= limit:
                return limit, "limit_triggered"
        else:
            if o <= limit:
                return o, "limit_gapped"
            if l <= limit:
                return limit, "limit_triggered"
        return None

    @staticmethod
    def _oco_priority(hit: tuple[WorkingOrder, Decimal, str]) -> tuple[int, int]:
        order, _, reason = hit
        gapped_first = 0 if reason.endswith("gapped") else 1
        stop_first = 0 if order.order_type == OrderType.STOP else 1
        return gapped_first, stop_first

    def _fill(self, result: BarExecution, order: WorkingOrder, bar: Bar, ref_price: Decimal, reason: str) -> bool:
        quantity = order.remaining
        if order.order_type == OrderType.MARKET:
            volume_cap = int(bar.volume * self.costs.max_volume_participation)
            quantity = min(quantity, volume_cap)
            if quantity <= 0:
                return False

        if order.order_type == OrderType.LIMIT:
            price = ref_price
        else:
            price = self.costs.with_slippage(ref_price, order.side)

        result.fills.append(SimFill(
            order_id=order.order_id,
            execution_id=f"sim-{order.order_id}-{bar.ts:%Y%m%dT%H%M%S}",
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=price,
            commission=self.costs.commission(quantity),
            ts=bar.ts,
            reason=reason,
        ))
        return True
