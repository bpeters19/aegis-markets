from decimal import Decimal

from app.engine.events import SignalAction, SignalEvent
from app.market_data.domain import Bar
from app.strategies.base import Strategy

TICK = Decimal("0.01")


def _sma(bars: tuple[Bar, ...]) -> Decimal:
    return sum((bar.close for bar in bars), Decimal(0)) / len(bars)


class MovingAverageCrossover(Strategy):
    """BUY when the fast SMA crosses above the slow SMA, SELL when it crosses below."""

    def __init__(
        self,
        fast: int = 10,
        slow: int = 30,
        stop_pct: Decimal = Decimal("0.05"),
        target_pct: Decimal = Decimal("0.10"),
    ) -> None:
        if not 0 < fast < slow:
            raise ValueError("windows must satisfy 0 < fast < slow")
        self.fast = fast
        self.slow = slow
        self.stop_pct = stop_pct
        self.target_pct = target_pct
        self.strategy_id = f"sma_cross_{fast}_{slow}"

    @property
    def lookback(self) -> int:
        return self.slow + 1

    def on_bar(self, bar: Bar, history: tuple[Bar, ...]) -> list[SignalEvent]:
        if len(history) < self.slow + 1:
            return []

        previous = history[:-1]
        fast_now, slow_now = _sma(history[-self.fast:]), _sma(history[-self.slow:])
        fast_prev, slow_prev = _sma(previous[-self.fast:]), _sma(previous[-self.slow:])
        price = bar.close

        if fast_prev <= slow_prev and fast_now > slow_now:
            return [SignalEvent(
                ts=bar.ts, symbol=bar.symbol, strategy_id=self.strategy_id,
                action=SignalAction.BUY, price=price,
                stop_loss=(price * (1 - self.stop_pct)).quantize(TICK),
                take_profit=(price * (1 + self.target_pct)).quantize(TICK),
                reason=f"SMA{self.fast} crossed above SMA{self.slow}",
            )]
        if fast_prev >= slow_prev and fast_now < slow_now:
            return [SignalEvent(
                ts=bar.ts, symbol=bar.symbol, strategy_id=self.strategy_id,
                action=SignalAction.SELL, price=price,
                reason=f"SMA{self.fast} crossed below SMA{self.slow}",
            )]
        return []
