import math
import statistics
from collections import deque

from app.market_data.domain import Bar

TRADING_DAYS = 252


class VolatilityTracker:
    """Rolling annualized volatility of daily close-to-close returns, per symbol."""

    def __init__(self, lookback: int = 20) -> None:
        if lookback < 2:
            raise ValueError("lookback must be at least 2 returns")
        self.lookback = lookback
        self._last_close: dict[str, float] = {}
        self._returns: dict[str, deque[float]] = {}

    def update(self, bar: Bar) -> None:
        close = float(bar.close)
        last = self._last_close.get(bar.symbol)
        if last:
            self._returns.setdefault(bar.symbol, deque(maxlen=self.lookback)).append(close / last - 1)
        self._last_close[bar.symbol] = close

    def annualized(self, symbol: str) -> float | None:
        returns = self._returns.get(symbol)
        if not returns or len(returns) < self.lookback:
            return None
        return statistics.stdev(returns) * math.sqrt(TRADING_DAYS)
