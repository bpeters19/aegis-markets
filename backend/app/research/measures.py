"""Measures used by hypotheses pre-registered after H1.

H1's evaluation keeps using evaluation.concentration (closed trades only) so its recorded result
never changes. New hypotheses use concentration_total, which also counts positions still open at
the end, as their pre-registrations specify."""
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.portfolio.engine import ClosedTrade


def profit_contributions(trades: Sequence[ClosedTrade], open_pnl: Mapping[str, Decimal]) -> list[float]:
    """Net profit of every closed trade plus every position still open at the end."""
    return [float(t.net_pnl) for t in trades] + [float(v) for v in open_pnl.values()]


def concentration_total(
    trades: Sequence[ClosedTrade], open_pnl: Mapping[str, Decimal]
) -> tuple[float | None, float | None]:
    """Best contribution and top 5 contributions as shares of total profit. None if there is no profit."""
    values = sorted(profit_contributions(trades, open_pnl), reverse=True)
    total = sum(values)
    if not values or total <= 0:
        return None, None
    return max(values[0], 0.0) / total, sum(v for v in values[:5] if v > 0) / total
