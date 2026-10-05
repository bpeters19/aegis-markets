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


class AlpacaError(RuntimeError):
    pass


def _to_rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetimes sent to Alpaca must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AlpacaProvider:
    def __init__(
        self,
        key_id: str,
        secret_key: str,
        base_url: str = "https://data.alpaca.markets",
        feed: str = "iex",
        adjustment: str = "split",
        client: httpx.Client | None = None,
        sleep: Callable[[float], Any] = time.sleep,
        max_retries: int = 3,
        page_limit: int = 10000,
    ) -> None:
        self.feed = feed
        self.adjustment = adjustment
        self.name = f"alpaca-{feed}-{adjustment}"
        self._client = client or httpx.Client(base_url=base_url, timeout=30.0)
        self._headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key}
        self._sleep = sleep
        self._max_retries = max_retries
        self._page_limit = page_limit

    @classmethod
    def from_settings(cls, settings: Settings) -> "AlpacaProvider":
        if not settings.alpaca_api_key_id or settings.alpaca_api_secret_key is None:
            raise AlpacaError("Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY in backend/.env")
        return cls(
            key_id=settings.alpaca_api_key_id,
            secret_key=settings.alpaca_api_secret_key.get_secret_value(),
            base_url=settings.alpaca_data_url,
            feed=settings.alpaca_feed,
            adjustment=settings.alpaca_adjustment,
        )

    def get_bars(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Bar]:
        symbol = symbol.strip().upper()
        params: dict[str, Any] = {
            "timeframe": timeframe.value,
            "start": _to_rfc3339(start),
            "end": _to_rfc3339(end),
            "limit": self._page_limit,
            "adjustment": self.adjustment,
            "feed": self.feed,
            "sort": "asc",
        }
        bars: list[Bar] = []
        skipped = 0
        while True:
            payload = self._get(f"/v2/stocks/{symbol}/bars", params)
            for raw in payload.get("bars") or []:
                bar = self._to_bar(symbol, timeframe, raw)
                if bar is None:
                    skipped += 1
                elif bar.ts < end:
                    bars.append(bar)
            token = payload.get("next_page_token")
            if not token:
                break
            params["page_token"] = token

        if skipped:
            logger.warning("Skipped %d invalid bars for %s %s", skipped, symbol, timeframe)
        return bars

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        last_error = ""
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(path, params=params, headers=self._headers)
            except httpx.TransportError as exc:
                last_error = f"network error: {exc}"
            else:
                status = response.status_code
                if status in (401, 403):
                    raise AlpacaError(f"Alpaca rejected the request ({status}). Check your API keys and data feed.")
                if status == 429 or status >= 500:
                    last_error = f"HTTP {status}"
                elif status >= 400:
                    raise AlpacaError(f"Alpaca error {status}: {response.text[:200]}")
                else:
                    return json.loads(response.content, parse_float=Decimal)

            if attempt < self._max_retries:
                delay = 2 ** attempt
                logger.warning("Alpaca request failed (%s), retrying in %ss", last_error, delay)
                self._sleep(delay)

        raise AlpacaError(f"Alpaca request failed after {self._max_retries} retries: {last_error}")

    @staticmethod
    def _to_bar(symbol: str, timeframe: Timeframe, raw: dict[str, Any]) -> Bar | None:
        try:
            return Bar(
                symbol=symbol,
                timeframe=timeframe,
                ts=raw["t"],
                open=Decimal(raw["o"]),
                high=Decimal(raw["h"]),
                low=Decimal(raw["l"]),
                close=Decimal(raw["c"]),
                volume=Decimal(raw["v"]),
            )
        except (KeyError, TypeError, ArithmeticError, ValidationError) as exc:
            logger.warning("Skipping invalid bar for %s: %s (%s)", symbol, raw, exc)
            return None
