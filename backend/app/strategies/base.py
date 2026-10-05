from abc import ABC, abstractmethod

from app.engine.events import SignalEvent
from app.market_data.domain import Bar


class Strategy(ABC):
    """A strategy turns the current bar plus past bars into signals.

    It never sees future data, never sizes positions, and never places orders.
    """

    strategy_id: str

    @property
    @abstractmethod
    def lookback(self) -> int:
        """How many bars of history (including the current bar) this strategy needs."""

    @abstractmethod
    def on_bar(self, bar: Bar, history: tuple[Bar, ...]) -> list[SignalEvent]:
        """history ends with the current bar and contains nothing newer."""
