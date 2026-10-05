import pytest

from app.engine.bus import EventBus
from app.engine.feed import HistoricalBarFeed
from tests.factories import series


def test_bus_processes_events_fifo_including_follow_ups():
    bus = EventBus()
    seen = []

    def on_str(event):
        seen.append(event)
        if event == "a":
            bus.publish(1)

    bus.subscribe(str, on_str)
    bus.subscribe(int, seen.append)
    bus.publish("a")
    bus.publish("b")
    bus.drain()
    assert seen == ["a", "b", 1]


def test_events_without_subscribers_are_dropped_quietly():
    bus = EventBus()
    bus.publish(3.5)
    assert bus.drain() == 1


def test_feed_merges_symbols_chronologically():
    feed = HistoricalBarFeed({"AAA": series([10, 11, 12], "AAA"), "BBB": series([20, 21, 22], "BBB")})
    order = [(bar.ts.day, bar.symbol) for bar in feed]
    assert order == [(1, "AAA"), (1, "BBB"), (2, "AAA"), (2, "BBB"), (3, "AAA"), (3, "BBB")]


def test_feed_rejects_out_of_order_bars():
    bars = series([10, 11, 12])
    bars[1], bars[2] = bars[2], bars[1]
    with pytest.raises(ValueError):
        list(HistoricalBarFeed({"TEST": bars}))
