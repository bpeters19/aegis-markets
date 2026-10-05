from app.engine.engine import SignalEngine
from app.engine.feed import HistoricalBarFeed
from app.strategies.base import Strategy
from tests.factories import series


class SpyStrategy(Strategy):
    strategy_id = "spy"

    def __init__(self):
        self.calls = []

    @property
    def lookback(self):
        return 3

    def on_bar(self, bar, history):
        self.calls.append((bar, history))
        return []


def test_strategy_never_sees_future_bars():
    closes = [10, 11, 12, 13, 14, 15, 16]
    spy = SpyStrategy()
    SignalEngine([spy]).run(HistoricalBarFeed({"TEST": series(closes)}))

    assert len(spy.calls) == len(closes)
    for bar, history in spy.calls:
        assert history[-1] == bar
        assert all(past.ts <= bar.ts for past in history)
        assert len(history) <= spy.lookback


def test_engine_never_reads_ahead_of_the_current_bar():
    bars = series([10, 11, 12, 13, 14])
    released = []

    def feed():
        for bar in bars:
            released.append(bar)
            yield bar

    class Checker(SpyStrategy):
        def on_bar(self, bar, history):
            assert released[-1] == bar, "engine pulled a future bar before finishing this one"
            return super().on_bar(bar, history)

    checker = Checker()
    SignalEngine([checker]).run(feed())
    assert len(checker.calls) == len(bars)


def test_history_is_per_symbol_and_immutable():
    spy = SpyStrategy()
    SignalEngine([spy]).run(
        HistoricalBarFeed({"AAA": series([10, 11, 12], "AAA"), "BBB": series([20, 21, 22], "BBB")})
    )
    for bar, history in spy.calls:
        assert {past.symbol for past in history} == {bar.symbol}
        assert isinstance(history, tuple)
