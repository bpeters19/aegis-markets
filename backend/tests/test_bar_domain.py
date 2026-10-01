from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.market_data.domain import Bar, Timeframe


def make_bar(**overrides):
    data = dict(
        symbol="nvda",
        timeframe=Timeframe.DAY_1,
        ts=datetime(2026, 1, 2, tzinfo=timezone.utc),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("99"),
        close=Decimal("104"),
        volume=Decimal("1000"),
    )
    data.update(overrides)
    return Bar(**data)


def test_symbol_is_normalized():
    assert make_bar().symbol == "NVDA"


def test_naive_timestamp_rejected():
    with pytest.raises(ValidationError):
        make_bar(ts=datetime(2026, 1, 2))


def test_timestamp_converted_to_utc():
    eastern = timezone(timedelta(hours=-5))
    bar = make_bar(ts=datetime(2026, 1, 2, 9, 30, tzinfo=eastern))
    assert bar.ts == datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    assert bar.ts.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "field, value",
    [
        ("high", Decimal("98")),
        ("open", Decimal("106")),
        ("close", Decimal("98")),
        ("volume", Decimal("-1")),
        ("low", Decimal("0")),
    ],
)
def test_inconsistent_bars_rejected(field, value):
    with pytest.raises(ValidationError):
        make_bar(**{field: value})
