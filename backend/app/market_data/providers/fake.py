from datetime import datetime, timedelta
from decimal import Decimal

from app.market_data.domain import Bar, Timeframe

STEP = {
    Timeframe.MINUTE_1: timedelta(minutes=1),
    Timeframe.MINUTE_5: timedelta(minutes=5),
    Timeframe.MINUTE_15: timedelta(minutes=15),
    Timeframe.HOUR_1: timedelta(hours=1),
    Timeframe.DAY_1: timedelta(days=1),
}


class FakeProvider:
    """Deterministic bars for tests and local development. Never touches the network."""

    name = "fake"

    def get_bars(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Bar]:
        bars = []
        price = Decimal("100.00")
        ts = start
        while ts < end:
            bars.append(
                Bar(
                    symbol=symbol,
                    timeframe=timeframe,
                    ts=ts,
                    open=price,
                    high=price + Decimal("1.00"),
                    low=price - Decimal("1.00"),
                    close=price + Decimal("0.50"),
                    volume=Decimal("1000"),
                )
            )
            price += Decimal("0.50")
            ts += STEP[timeframe]
        return bars
