from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.main import app
from app.market_data.domain import Timeframe
from app.market_data.models import BarRecord
from app.market_data.providers.fake import FakeProvider
from app.market_data.service import ingest_bars

client = TestClient(app)
SYMBOL = "ZZAPI"


def request_body(**overrides):
    body = {"symbols": [SYMBOL], "start": "2026-01-15", "end": "2026-03-01",
            "fast": 2, "slow": 3, "benchmark": SYMBOL, "cash_rate": "0"}
    body.update(overrides)
    return body


def test_rejects_fast_window_not_shorter_than_slow():
    assert client.post("/api/v1/backtests", json=request_body(fast=30, slow=10)).status_code == 422


def test_rejects_start_after_end():
    assert client.post("/api/v1/backtests", json=request_body(start="2026-03-01", end="2026-01-15")).status_code == 422


def test_rejects_too_many_symbols():
    symbols = [f"S{i}" for i in range(11)]
    assert client.post("/api/v1/backtests", json=request_body(symbols=symbols)).status_code == 422


@pytest.fixture
def stored_bars():
    with Session(get_engine()) as session:
        session.execute(delete(BarRecord).where(BarRecord.symbol == SYMBOL))
        ingest_bars(session, FakeProvider(), SYMBOL, Timeframe.DAY_1,
                    datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 3, 1, tzinfo=timezone.utc))
        yield
        session.execute(delete(BarRecord).where(BarRecord.symbol == SYMBOL))
        session.commit()


@pytest.mark.integration
def test_symbols_lists_stored_data(stored_bars):
    body = client.get("/api/v1/symbols").json()
    row = next(r for r in body if r["symbol"] == SYMBOL)
    assert row["bars"] == 59
    assert row["timeframe"] == "1Day"


@pytest.mark.integration
def test_backtest_returns_curve_metrics_and_benchmark(stored_bars):
    response = client.post("/api/v1/backtests", json=request_body())
    assert response.status_code == 200
    body = response.json()

    assert body["trading_days"] == 45
    assert len(body["equity_curve"]) == 45
    assert body["equity_curve"][0]["equity"] == "100000.00"
    assert body["strategy"]["total_return"] == 0
    assert body["strategy"]["sharpe"] is None
    assert body["benchmark"]["total_return"] > 0
    assert body["trades"] == []
