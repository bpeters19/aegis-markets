from collections import deque

from app.market_data.domain import Bar


class BarHistory:
    """Rolling per-symbol window of bars the engine has already released.

    This is the only market data a strategy ever receives.
    """

    def __init__(self, maxlen: int) -> None:
        if maxlen < 1:
            raise ValueError("maxlen must be at least 1")
        self._maxlen = maxlen
        self._bars: dict[str, deque[Bar]] = {}

    def append(self, bar: Bar) -> None:
        window = self._bars.setdefault(bar.symbol, deque(maxlen=self._maxlen))
        if window and bar.ts <= window[-1].ts:
            raise ValueError(f"Out-of-order bar for {bar.symbol}: {bar.ts} is not after {window[-1].ts}")
        window.append(bar)

    def view(self, symbol: str) -> tuple[Bar, ...]:
        return tuple(self._bars.get(symbol, ()))
