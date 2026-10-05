from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    quantity: int
    avg_price: Decimal
    market_price: Decimal

    @property
    def market_value(self) -> Decimal:
        return self.market_price * self.quantity


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Read-only view of the portfolio at one moment. The risk engine only ever sees this."""

    cash: Decimal
    positions: Mapping[str, Position]
    start_of_day_equity: Decimal

    @property
    def equity(self) -> Decimal:
        return self.cash + sum((p.market_value for p in self.positions.values()), Decimal(0))

    @property
    def gross_exposure(self) -> Decimal:
        return sum((abs(p.market_value) for p in self.positions.values()), Decimal(0))

    @property
    def daily_pnl_pct(self) -> Decimal:
        if self.start_of_day_equity <= 0:
            return Decimal(0)
        return (self.equity - self.start_of_day_equity) / self.start_of_day_equity
