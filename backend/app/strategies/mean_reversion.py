from decimal import Decimal

from app.engine.events import SignalAction, SignalEvent
from app.indicators.rsi import wilder_rsi
from app.market_data.domain import Bar
from app.strategies.base import Strategy


def _mean(bars: tuple[Bar, ...]) -> Decimal:
    return sum((b.close for b in bars), Decimal(0)) / len(bars)


class MeanReversion(Strategy):
    """Buy short-term dips in assets that are in a long-term uptrend; exit on the bounce or after a time limit.

    Entry: RSI(rsi_period) below entry_threshold and close above its trend_window average.
    Exit:  close above its exit_window average, or max_hold_days trading days after the entry signal.
    The strategy tracks its own entries to apply the time limit.
    """

    def __init__(
        self,
        entry_threshold: float = 10,
        rsi_period: int = 2,
        trend_window: int = 200,
        exit_window: int = 5,
        max_hold_days: int = 10,
    ) -> None:
        if not 0 < entry_threshold < 100:
            raise ValueError("entry_threshold must be between 0 and 100")
        if rsi_period < 1 or trend_window < 2 or exit_window < 2 or max_hold_days < 1:
            raise ValueError("periods and windows must be positive")
        self.entry_threshold = entry_threshold
        self.rsi_period = rsi_period
        self.trend_window = trend_window
        self.exit_window = exit_window
        self.max_hold_days = max_hold_days
        self.strategy_id = f"meanrev_rsi{rsi_period}_{entry_threshold:g}"
        self._bars_seen: dict[str, int] = {}
        self._entry_bar: dict[str, int] = {}

    @property
    def lookback(self) -> int:
        return max(self.trend_window, self.exit_window, self.rsi_period) + 1

    def on_bar(self, bar: Bar, history: tuple[Bar, ...]) -> list[SignalEvent]:
        count = self._bars_seen.get(bar.symbol, 0) + 1
        self._bars_seen[bar.symbol] = count
        if len(history) < self.lookback:
            return []

        if bar.symbol in self._entry_bar:
            days_held = count - self._entry_bar[bar.symbol]
            if bar.close > _mean(history[-self.exit_window:]):
                reason = f"close above {self.exit_window}-day average"
            elif days_held >= self.max_hold_days:
                reason = f"{self.max_hold_days}-day time limit"
            else:
                return []
            del self._entry_bar[bar.symbol]
            return [self._signal(bar, SignalAction.SELL, reason)]

        rsi = wilder_rsi([b.close for b in history], self.rsi_period)
        if rsi is not None and rsi < self.entry_threshold and bar.close > _mean(history[-self.trend_window:]):
            self._entry_bar[bar.symbol] = count
            return [self._signal(bar, SignalAction.BUY, f"RSI({self.rsi_period}) {rsi:.1f} in uptrend")]
        return []

    def _signal(self, bar: Bar, action: SignalAction, reason: str) -> SignalEvent:
        return SignalEvent(
            ts=bar.ts, symbol=bar.symbol, strategy_id=self.strategy_id,
            action=action, price=bar.close, reason=reason,
        )
