from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.market_data.domain import Bar, Timeframe

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_bar(close, day=0, symbol="TEST"):
    c = Decimal(str(close))
    return Bar(
        symbol=symbol, timeframe=Timeframe.DAY_1, ts=BASE + timedelta(days=day),
        open=c, high=c + 1, low=c - 1, close=c, volume=Decimal("1000"),
    )


def series(closes, symbol="TEST"):
    return [make_bar(close, day=i, symbol=symbol) for i, close in enumerate(closes)]
