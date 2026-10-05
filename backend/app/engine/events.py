from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.market_data.domain import Bar


class SignalAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class BarEvent:
    bar: Bar

    @property
    def ts(self) -> datetime:
        return self.bar.ts


@dataclass(frozen=True, slots=True)
class SignalEvent:
    ts: datetime
    symbol: str
    strategy_id: str
    action: SignalAction
    price: Decimal
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    reason: str = ""
