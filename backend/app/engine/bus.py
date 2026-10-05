from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

Handler = Callable[[Any], None]


class EventBus:
    """Synchronous FIFO event bus.

    Handlers can publish new events. Those are queued and processed in order,
    never run re-entrantly, so event ordering is always deterministic.
    """

    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)
        self._queue: deque[Any] = deque()

    def subscribe(self, event_type: type, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        self._queue.append(event)

    def drain(self) -> int:
        processed = 0
        while self._queue:
            event = self._queue.popleft()
            for handler in self._handlers.get(type(event), []):
                handler(event)
            processed += 1
        return processed
