import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.market_data.domain import Bar, Timeframe

logger = logging.getLogger(__name__)

ADJUSTED_FIELDS = ("adjOpen", "adjHigh", "adjLow", "adjClose", "adjVolume")
RAW_FIELDS = ("open", "high", "low", "close", "volume")


class TiingoError(RuntimeError):
    pass


def _to_date(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetimes sent to Tiingo must be timezone-aware")
    return value.astimezone(timezone.utc).date().isoformat()


class TiingoProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.tiingo.com",
        adjusted: bool = True,
        client: httpx.Client | None = None,
        sleep: Callable[[float], Any] = time.sleep,
        max_retries: int = 3,
    ) -> None:
        self.adjusted = adjusted
        self.name = "tiingo-adjusted" if adjusted else "tiingo-raw"
        self._client = client or httpx.Client(base_url=base_url, timeout=30.0)
        self._headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
        self._sleep = sleep
        self._max_retries = max_retries

    @classmethod
    def from_settings(cls, settings: Settings) -> "TiingoProvider":
        if settings.tiingo_api_key is None:
            raise TiingoError("Set TIINGO_API_KEY in backend/.env")
        return cls(
            api_key=settings.tiingo_api_key.get_secret_value(),
            base_url=settings.tiingo_base_url,
            adjusted=settings.tiingo_adjusted,
        )

    def get_bars(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Bar]:
        if timeframe != Timeframe.DAY_1:
            raise TiingoError("Tiingo end-of-day data only supports daily bars (1Day)")
        symbol = symbol.strip().upper()
        params = {"startDate": _to_date(start), "endDate": _to_date(end)}
        rows = self._get(f"/tiingo/daily/{symbol.lower()}/prices", params)

        bars: list[Bar] = []
        skipped = 0
        for raw in rows:
            bar = self._to_bar(symbol, raw)
            if bar is None:
                skipped += 1
            elif start <= bar.ts < end:
                bars.append(bar)

        if skipped:
            logger.warning("Skipped %d invalid bars for %s", skipped, symbol)
        return bars

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        last_error = ""
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(path, params=params, headers=self._headers)
            except httpx.TransportError as exc:
                last_error = f"network error: {exc}"
            else:
                status = response.status_code
                if status in (401, 403):
                    raise TiingoError(f"Tiingo rejected the request ({status}). Check TIINGO_API_KEY.")
                if status == 429 or status >= 500:
                    last_error = f"HTTP {status}"
                elif status >= 400:
                    raise TiingoError(f"Tiingo error {status}: {response.text[:200]}")
                else:
                    return json.loads(response.content, parse_float=Decimal)

            if attempt < self._max_retries:
                delay = 2 ** attempt
                logger.warning("Tiingo request failed (%s), retrying in %ss", last_error, delay)
                self._sleep(delay)

        raise TiingoError(f"Tiingo request failed after {self._max_retries} retries: {last_error}")

    def _to_bar(self, symbol: str, raw: dict[str, Any]) -> Bar | None:
        fields = ADJUSTED_FIELDS if self.adjusted else RAW_FIELDS
        try:
            o, h, l, c, v = (Decimal(raw[name]) for name in fields)
            return Bar(
                symbol=symbol, timeframe=Timeframe.DAY_1, ts=raw["date"],
                open=o, high=h, low=l, close=c, volume=v,
            )
        except (KeyError, TypeError, ArithmeticError, ValidationError) as exc:
            logger.warning("Skipping invalid bar for %s: %s (%s)", symbol, raw, exc)
            return None
