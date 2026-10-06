from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.market_data.domain import Bar
from app.oms.states import OrderSide
from app.portfolio.snapshot import PortfolioSnapshot, Position

ACCOUNTING_TOLERANCE = Decimal("0.000001")


class AccountingError(RuntimeError):
    pass


@dataclass
class OpenPosition:
    symbol: str
    opened_at: datetime
    quantity: int = 0
    avg_cost: Decimal = Decimal(0)
    market_price: Decimal = Decimal(0)
    max_quantity: int = 0
    gross_pnl: Decimal = Decimal(0)
    commissions: Decimal = Decimal(0)
    exit_value: Decimal = Decimal(0)
    exit_quantity: int = 0


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    symbol: str
    opened_at: datetime
    closed_at: datetime
    quantity: int
    avg_entry: Decimal
    avg_exit: Decimal
    gross_pnl: Decimal
    commissions: Decimal
    exit_reason: str

    @property
    def net_pnl(self) -> Decimal:
        return self.gross_pnl - self.commissions


class Portfolio:
    """Long-only portfolio with average-cost accounting.

    Cash, positions and P&L change only through apply_fill(); prices only through mark().
    check_accounting() verifies equity == starting cash + realized + unrealized - commissions.
    """

    def __init__(self, starting_cash: Decimal) -> None:
        if starting_cash <= 0:
            raise ValueError("starting cash must be positive")
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.positions: dict[str, OpenPosition] = {}
        self.realized_pnl = Decimal(0)
        self.commissions = Decimal(0)
        self.trades: list[ClosedTrade] = []
        self.equity_curve: list[tuple[date, Decimal]] = []
        self.start_of_day_equity = starting_cash
        self._day: date | None = None

    @property
    def market_value(self) -> Decimal:
        return sum((p.market_price * p.quantity for p in self.positions.values()), Decimal(0))

    @property
    def equity(self) -> Decimal:
        return self.cash + self.market_value

    @property
    def unrealized_pnl(self) -> Decimal:
        return sum(((p.market_price - p.avg_cost) * p.quantity for p in self.positions.values()), Decimal(0))

    def start_bar(self, bar: Bar) -> None:
        day = bar.ts.date()
        if day != self._day:
            self.close_day()
            self._day = day
            self.start_of_day_equity = self.equity

    def close_day(self) -> None:
        if self._day is not None and (not self.equity_curve or self.equity_curve[-1][0] != self._day):
            self.equity_curve.append((self._day, self.equity))

    def mark(self, bar: Bar) -> None:
        position = self.positions.get(bar.symbol)
        if position is not None:
            position.market_price = bar.close

    def apply_fill(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: Decimal,
        commission: Decimal,
        ts: datetime,
        reason: str = "",
    ) -> ClosedTrade | None:
        if quantity <= 0 or price <= 0 or commission < 0:
            raise ValueError("fill quantity and price must be positive and commission non-negative")
        position = self.positions.get(symbol)

        if side == OrderSide.SELL:
            held = position.quantity if position else 0
            if quantity > held:
                raise ValueError(f"cannot sell {quantity} {symbol}, holding {held} (short selling is not supported)")

        self.cash -= commission
        self.commissions += commission

        if side == OrderSide.BUY:
            if position is None:
                position = self.positions[symbol] = OpenPosition(symbol, opened_at=ts)
            total = position.quantity + quantity
            position.avg_cost = (position.avg_cost * position.quantity + price * quantity) / total
            position.quantity = total
            position.max_quantity = max(position.max_quantity, total)
            position.market_price = price
            position.commissions += commission
            self.cash -= price * quantity
            return None

        pnl = (price - position.avg_cost) * quantity
        self.realized_pnl += pnl
        self.cash += price * quantity
        position.gross_pnl += pnl
        position.commissions += commission
        position.exit_value += price * quantity
        position.exit_quantity += quantity
        position.quantity -= quantity
        if position.quantity > 0:
            return None

        del self.positions[symbol]
        trade = ClosedTrade(
            symbol=symbol,
            opened_at=position.opened_at,
            closed_at=ts,
            quantity=position.max_quantity,
            avg_entry=position.avg_cost,
            avg_exit=position.exit_value / position.exit_quantity,
            gross_pnl=position.gross_pnl,
            commissions=position.commissions,
            exit_reason=reason,
        )
        self.trades.append(trade)
        return trade

    def snapshot(self, pending_buys: Iterable[tuple[str, int, Decimal]] = ()) -> PortfolioSnapshot:
        """Risk view of the portfolio. Working buy orders count as positions and reserve cash."""
        positions = {s: Position(s, p.quantity, p.avg_cost, p.market_price) for s, p in self.positions.items()}
        cash = self.cash
        for symbol, quantity, price in pending_buys:
            held = positions[symbol].quantity if symbol in positions else 0
            positions[symbol] = Position(symbol, held + quantity, price, price)
            cash -= quantity * price
        return PortfolioSnapshot(cash, positions, self.start_of_day_equity)

    def check_accounting(self) -> None:
        expected = self.starting_cash + self.realized_pnl + self.unrealized_pnl - self.commissions
        if abs(self.equity - expected) > ACCOUNTING_TOLERANCE:
            raise AccountingError(
                f"equity {self.equity} != starting cash + realized + unrealized - commissions ({expected})"
            )
