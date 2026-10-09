from app.engine.events import SignalAction, SignalEvent
from app.market_data.domain import Bar
from app.strategies.base import Strategy


class TimeSeriesMomentum(Strategy):
    """Hold an asset while its own trailing return is positive.

    Evaluates only on the first trading day of each month, detected from the previous bar
    (never by looking ahead), and emits the target state at every evaluation: BUY when the
    trailing return is positive, SELL when it is zero or negative. No stops or targets.
    """

    def __init__(self, lookback_days: int) -> None:
        if lookback_days < 1:
            raise ValueError("lookback_days must be at least 1")
        self.lookback_days = lookback_days
        self.strategy_id = f"tsmom_{lookback_days}"

    @property
    def lookback(self) -> int:
        return self.lookback_days + 1

    def on_bar(self, bar: Bar, history: tuple[Bar, ...]) -> list[SignalEvent]:
        if len(history) < self.lookback:
            return []
        previous = history[-2]
        if (previous.ts.year, previous.ts.month) == (bar.ts.year, bar.ts.month):
            return []

        trailing = bar.close / history[-1 - self.lookback_days].close - 1
        action = SignalAction.BUY if trailing > 0 else SignalAction.SELL
        return [SignalEvent(
            ts=bar.ts,
            symbol=bar.symbol,
            strategy_id=self.strategy_id,
            action=action,
            price=bar.close,
            reason=f"{self.lookback_days}-day return {trailing:+.2%}",
        )]
