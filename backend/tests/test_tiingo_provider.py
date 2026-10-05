from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from app.market_data.domain import Timeframe
from app.market_data.providers.tiingo import TiingoError, TiingoProvider

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 10, tzinfo=timezone.utc)


def row(date, close=187.32, adj_close=93.66, high=188.0, adj_high=94.0):
    return {
        "date": date, "open": 187.0, "high": high, "low": 186.5, "close": close, "volume": 1000,
        "adjOpen": 93.5, "adjHigh": adj_high, "adjLow": 93.25, "adjClose": adj_close, "adjVolume": 2000,
        "divCash": 0.0, "splitFactor": 1.0,
    }


def make_provider(handler, adjusted=True):
    client = httpx.Client(base_url="https://tiingo.test", transport=httpx.MockTransport(handler))
    sleeps = []
    provider = TiingoProvider("test-key", adjusted=adjusted, client=client, sleep=sleeps.append)
    return provider, sleeps


def test_parses_adjusted_bars_with_exact_decimals():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(200, json=[row("2026-01-02T00:00:00.000Z")])

    provider, _ = make_provider(handler)
    bars = provider.get_bars("NVDA", Timeframe.DAY_1, START, END)

    assert len(bars) == 1
    assert bars[0].close == Decimal("93.66")
    assert bars[0].volume == Decimal("2000")
    assert seen["path"] == "/tiingo/daily/nvda/prices"
    assert seen["params"] == {"startDate": "2026-01-01", "endDate": "2026-01-10"}
    assert seen["auth"] == "Token test-key"
    assert provider.name == "tiingo-adjusted"


def test_raw_mode_uses_unadjusted_prices():
    provider, _ = make_provider(lambda request: httpx.Response(200, json=[row("2026-01-02T00:00:00.000Z")]), adjusted=False)
    bars = provider.get_bars("NVDA", Timeframe.DAY_1, START, END)
    assert bars[0].close == Decimal("187.32")
    assert provider.name == "tiingo-raw"


def test_intraday_timeframe_rejected_before_any_request():
    calls = []
    provider, _ = make_provider(lambda request: calls.append(1))
    with pytest.raises(TiingoError):
        provider.get_bars("NVDA", Timeframe.MINUTE_1, START, END)
    assert calls == []


def test_skips_invalid_bars_and_keeps_the_rest():
    bad = row("2026-01-02T00:00:00.000Z", adj_high=90.0)
    good = row("2026-01-05T00:00:00.000Z")
    provider, _ = make_provider(lambda request: httpx.Response(200, json=[bad, good]))
    bars = provider.get_bars("NVDA", Timeframe.DAY_1, START, END)
    assert len(bars) == 1
    assert bars[0].ts == datetime(2026, 1, 5, tzinfo=timezone.utc)


def test_end_boundary_is_excluded():
    rows = [row("2026-01-02T00:00:00.000Z"), row("2026-01-10T00:00:00.000Z")]
    provider, _ = make_provider(lambda request: httpx.Response(200, json=rows))
    assert len(provider.get_bars("NVDA", Timeframe.DAY_1, START, END)) == 1


def test_retries_rate_limit_with_backoff():
    responses = iter([httpx.Response(429), httpx.Response(200, json=[row("2026-01-02T00:00:00.000Z")])])
    provider, sleeps = make_provider(lambda request: next(responses))
    assert len(provider.get_bars("NVDA", Timeframe.DAY_1, START, END)) == 1
    assert sleeps == [1]


def test_bad_token_fails_fast_without_retrying():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401)

    provider, sleeps = make_provider(handler)
    with pytest.raises(TiingoError):
        provider.get_bars("NVDA", Timeframe.DAY_1, START, END)
    assert len(calls) == 1
    assert sleeps == []
