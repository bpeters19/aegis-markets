from datetime import timedelta

from app.backtest.research import window
from tests.factories import BASE, series


def test_window_keeps_warmup_bars_before_start():
    bars = series([10] * 10)
    picked = window(bars, BASE + timedelta(days=5), BASE + timedelta(days=8), warmup=3)
    assert [b.ts.day for b in picked] == [3, 4, 5, 6, 7, 8]
