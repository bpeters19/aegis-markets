"""Deterministic replay of a paper account from its start date. State is recomputed, never stored."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.research import window
from app.database.session import get_engine
from app.market_data.domain import Bar
from app.oms.models import FillRecord, OrderRecord
from app.research.config import HypothesisConfig, ParamVariant
from app.research.evaluation import STRATEGIES, at
from app.research.satellite import build_strategy
from app.strategies.base import Strategy
from app.trading.pipeline import TradingPipeline

PRECISION = Decimal("0.000001")


@dataclass(frozen=True)
class ReplayDay:
    day: date
    equity: Decimal
    cash: Decimal
    exposure: Decimal
    positions: dict[str, int]
    fills: list[dict[str, Any]]
    orders: list[dict[str, Any]]


def build(config: HypothesisConfig) -> Strategy:
    if isinstance(config.primary, ParamVariant):
        return build_strategy(config, config.primary)
    return STRATEGIES[config.strategy](config.primary.lookback_days)


def _role(order: OrderRecord) -> str:
    if order.client_order_id.endswith(":SL"):
        return "stop"
    if order.client_order_id.endswith(":TP"):
        return "target"
    return "entry" if order.side == "BUY" else "exit"


def replay(
    config: HypothesisConfig, start: date, capital: Decimal, series: dict[str, list[Bar]], through: date
) -> list[ReplayDay]:
    strategy = build(config)
    warmup = max(strategy.lookback, config.volatility_lookback + 1)
    end = at(through + timedelta(days=1))
    sliced = {s: window(b, at(start), end, warmup) for s, b in series.items()}
    sliced = {s: b for s, b in sliced.items() if b}

    # Idle cash earns interest during warm-up; start smaller so equity on the start date equals capital.
    warmup_days = len({b.ts.date() for bars in sliced.values() for b in bars if b.ts.date() < start})
    growth = (Decimal(1) + config.cash_rate / Decimal(252)) ** warmup_days

    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        pipeline = TradingPipeline(
            session, [strategy], starting_cash=capital / growth, limits=config.limits, costs=config.costs,
            cash_rate=config.cash_rate, trade_from=at(start), volatility_lookback=config.volatility_lookback,
        )
        pipeline.run(sliced)

        prefix = f"{pipeline.run_id}:%"
        fills: dict[date, list[dict[str, Any]]] = {}
        for fill, order in session.execute(
            select(FillRecord, OrderRecord).join(OrderRecord, FillRecord.order_id == OrderRecord.id)
            .where(OrderRecord.client_order_id.like(prefix)).order_by(FillRecord.id)
        ).all():
            fills.setdefault(fill.filled_at.date(), []).append({
                "symbol": order.symbol, "side": str(order.side), "role": _role(order),
                "quantity": fill.quantity, "price": str(fill.price),
            })

        orders: dict[date, list[dict[str, Any]]] = {}
        for order in session.scalars(
            select(OrderRecord).where(OrderRecord.client_order_id.like(prefix))
            .order_by(OrderRecord.created_at, OrderRecord.symbol)
        ):
            role = _role(order)
            if role in ("entry", "exit"):  # brackets are placed at fill time, not after the close
                placed_after = (order.created_at - timedelta(days=1)).date()
                orders.setdefault(placed_after, []).append({
                    "symbol": order.symbol, "side": str(order.side), "role": role,
                    "quantity": order.quantity, "type": str(order.order_type),
                })
    finally:
        session.close()
        transaction.rollback()
        connection.close()

    pf = pipeline.portfolio
    equity = dict(pf.equity_curve)
    exposure = dict(pf.exposure_curve)
    return [
        ReplayDay(
            day=d, equity=equity[d].quantize(PRECISION), cash=cash.quantize(PRECISION),
            exposure=exposure[d].quantize(PRECISION), positions=positions,
            fills=fills.get(d, []), orders=orders.get(d, []),
        )
        for d, cash, positions in pf.daily_positions
        if start <= d <= through
    ]
