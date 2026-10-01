from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.main import app
from app.market_data.domain import Bar, Timeframe
from app.market_data.models import BarRecord
from app.market_data.providers.fake import FakeProvider
from app.market_data.repository import fetch_bars, upsert_bars
from app.market_data.service import ingest_bars

pytestmark = pytest.mark.integration

SYMBOL = "ZZTEST"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 11, tzinfo=timezone.utc)


def clear(session: Session) -> None:
    session.execute(delete(BarRecord).where(BarRecord.symbol == SYMBOL))
    session.commit()


@pytest.fixture
def session():
    with Session(get_engine()) as s:
        clear(s)
        yield s
        s.rollback()
        clear(s)


def test_ingest_is_idempotent(session):
    provider = FakeProvider()
    first = ingest_bars(session, provider, SYMBOL, Timeframe.DAY_1, START, END)
    second = ingest_bars(session, provider, SYMBOL, Timeframe.DAY_1, START, END)
    stored = fetch_bars(session, SYMBOL, Timeframe.DAY_1, START, END, limit=100)
    assert first == second == 10
    assert len(stored) == 10


def test_upsert_applies_vendor_corrections(session):
    ingest_bars(session, FakeProvider(), SYMBOL, Timeframe.DAY_1, START, END)
    original = fetch_bars(session, SYMBOL, Timeframe.DAY_1, START, END, limit=1)[0]
    corrected = Bar(
        symbol=SYMBOL, timeframe=Timeframe.DAY_1, ts=original.ts,
        open=original.open, high=original.high, low=original.low,
        close=original.low, volume=Decimal("5000"),
    )
    expected_close = original.low
    upsert_bars(session, [corrected], source="fake")
    session.commit()
    session.expire_all()
    updated = fetch_bars(session, SYMBOL, Timeframe.DAY_1, START, END, limit=1)[0]
    assert updated.close == expected_close
    assert updated.volume == Decimal("5000")


def test_bars_endpoint_returns_ordered_bars(session):
    ingest_bars(session, FakeProvider(), SYMBOL, Timeframe.DAY_1, START, END)
    client = TestClient(app)
    response = client.get(
        "/api/v1/bars",
        params={"symbol": SYMBOL.lower(), "timeframe": "1Day",
                "start": START.isoformat(), "end": END.isoformat()},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 10
    timestamps = [bar["ts"] for bar in body]
    assert timestamps == sorted(timestamps)
    assert Decimal(body[0]["close"]) == Decimal("100.5")
