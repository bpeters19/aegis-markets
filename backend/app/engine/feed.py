import heapq
from collections.abc import Iterator, Mapping, Sequence

from app.market_data.domain import Bar, Timeframe
from app.market_data.models import BarRecord


def bar_from_record(record: BarRecord) -> Bar:
    return Bar(
        symbol=record.symbol,
        timeframe=Timeframe(record.timeframe),
        ts=record.ts,
        open=record.open,
        high=record.high,
        low=record.low,
        close=record.close,
        volume=record.volume,
    )


class HistoricalBarFeed:
    """Replays per-symbol bar series as one chronological stream (k-way merge)."""

    def __init__(self, series: Mapping[str, Sequence[Bar]]) -> None:
        self._series = series

    def __iter__(self) -> Iterator[Bar]:
        merged = heapq.merge(*self._series.values(), key=lambda bar: (bar.ts, bar.symbol))
        previous: Bar | None = None
        for bar in merged:
            if previous is not None and (bar.ts, bar.symbol) <= (previous.ts, previous.symbol):
                raise ValueError(
                    f"Feed out of order: {bar.symbol} {bar.ts} after {previous.symbol} {previous.ts}"
                )
            previous = bar
            yield bar
