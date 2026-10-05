from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from app.engine.bus import EventBus
from app.engine.events import BarEvent, SignalEvent
from app.engine.history import BarHistory
from app.market_data.domain import Bar
from app.strategies.base import Strategy


@dataclass
class EngineResult:
    bars_processed: int = 0
    signals: list[SignalEvent] = field(default_factory=list)


class SignalEngine:
    """Replays bars one at a time through strategies.

    Every event caused by bar t is fully processed before bar t+1 is read
    from the feed, so no component can ever act on future data.
    """

    def __init__(self, strategies: Sequence[Strategy]) -> None:
        if not strategies:
            raise ValueError("at least one strategy is required")
        self.bus = EventBus()
        self._strategies = list(strategies)
        self._history = BarHistory(max(s.lookback for s in self._strategies))
        self._result = EngineResult()
        self.bus.subscribe(BarEvent, self._on_bar)
        self.bus.subscribe(SignalEvent, self._result.signals.append)

    def _on_bar(self, event: BarEvent) -> None:
        self._history.append(event.bar)
        window = self._history.view(event.bar.symbol)
        for strategy in self._strategies:
            for signal in strategy.on_bar(event.bar, window[-strategy.lookback:]):
                self.bus.publish(signal)

    def run(self, feed: Iterable[Bar]) -> EngineResult:
        for bar in feed:
            self.bus.publish(BarEvent(bar))
            self.bus.drain()
            self._result.bars_processed += 1
        return self._result
