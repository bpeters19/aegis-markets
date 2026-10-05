from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from app.market_data.domain import Timeframe
from app.market_data.providers.alpaca import AlpacaError, AlpacaProvider

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 10, tzinfo=timezone.utc)


def raw_bar(t, o=187.0, h=188.0, l=186.5, c=187.32, v=1000):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


def make_provider(handler):
    client = httpx.Client(base_url="https://data.test", transport=httpx.MockTransport(handler))
    sleeps = []
    provider = AlpacaProvider("test-key", "test-secret", client=client, sleep=sleeps.append)
    return provider, sleeps


def test_parses_bars_with_exact_decimals_and_sends_auth():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["key"] = request.headers["APCA-API-KEY-ID"]
        return httpx.Response(200, json={"bars": [raw_bar("2026-01-02T05:00:00Z")], "next_page_token": None})

    provider, _ = make_provider(handler)
    bars = provider.get_bars("nvda", Timeframe.DAY_1, START, END)

    assert len(bars) == 1
    assert bars[0].close == Decimal("187.32")
    assert seen["path"] == "/v2/stocks/NVDA/bars"
    assert seen["params"]["timeframe"] == "1Day"
    assert seen["params"]["feed"] == "iex"
    assert seen["params"]["start"] == "2026-01-01T00:00:00Z"
    assert seen["key"] == "test-key"
    assert provider.name == "alpaca-iex-split"


def test_follows_pagination():
    calls = []

    def handler(request):
        calls.append(dict(request.url.params))
        if "page_token" not in request.url.params:
            return httpx.Response(200, json={"bars": [raw_bar("2026-01-02T05:00:00Z")], "next_page_token": "abc"})
        return httpx.Response(200, json={"bars": [raw_bar("2026-01-05T05:00:00Z")], "next_page_token": None})

    provider, _ = make_provider(handler)
    bars = provider.get_bars("NVDA", Timeframe.DAY_1, START, END)

    assert len(bars) == 2
    assert len(calls) == 2
    assert calls[1]["page_token"] == "abc"


def test_skips_invalid_bars_and_keeps_the_rest():
    def handler(request):
        bad = raw_bar("2026-01-02T05:00:00Z", h=180.0)
        good = raw_bar("2026-01-05T05:00:00Z")
        return httpx.Response(200, json={"bars": [bad, good], "next_page_token": None})

    provider, _ = make_provider(handler)
    bars = provider.get_bars("NVDA", Timeframe.DAY_1, START, END)

    assert len(bars) == 1
    assert bars[0].ts == datetime(2026, 1, 5, 5, tzinfo=timezone.utc)


def test_retries_rate_limit_with_backoff():
    responses = iter([
        httpx.Response(429),
        httpx.Response(200, json={"bars": [raw_bar("2026-01-02T05:00:00Z")], "next_page_token": None}),
    ])

    provider, sleeps = make_provider(lambda request: next(responses))
    bars = provider.get_bars("NVDA", Timeframe.DAY_1, START, END)

    assert len(bars) == 1
    assert sleeps == [1]


def test_bad_credentials_fail_fast_without_retrying():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401)

    provider, sleeps = make_provider(handler)
    with pytest.raises(AlpacaError):
        provider.get_bars("NVDA", Timeframe.DAY_1, START, END)
    assert len(calls) == 1
    assert sleeps == []


def test_end_boundary_is_excluded():
    def handler(request):
        bars = [raw_bar("2026-01-02T05:00:00Z"), raw_bar("2026-01-10T00:00:00Z")]
        return httpx.Response(200, json={"bars": bars, "next_page_token": None})

    provider, _ = make_provider(handler)
    bars = provider.get_bars("NVDA", Timeframe.DAY_1, START, END)

    assert len(bars) == 1
