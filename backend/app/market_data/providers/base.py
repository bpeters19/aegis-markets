from datetime import datetime
from typing import Protocol

from app.market_data.domain import Bar, Timeframe


class MarketDataProvider(Protocol):
    name: str

    def get_bars(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Bar]: ...
