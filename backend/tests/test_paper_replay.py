from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.paper.ledger import DayState, find_drift
from app.paper.replay import replay
from app.paper.run import complete_through
from app.research.config import Variant
from app.research.hypotheses.h1 import H1
from tests.factories import series

TEST_CONFIG = replace(H1, universe=("AAA",), benchmark="AAA", primary=Variant("test", 3), volatility_lookback=2)
START, THROUGH = date(2026, 2, 1), date(2026, 3, 10)


def test_a_day_is_complete_only_after_6pm_new_york():
    assert complete_through(datetime(2026, 10, 12, 21, 0, tzinfo=timezone.utc)) == date(2026, 10, 11)  # 5 PM ET
    assert complete_through(datetime(2026, 10, 12, 23, 0, tzinfo=timezone.utc)) == date(2026, 10, 12)  # 7 PM ET


def run_replay():
    bars = {"AAA": series([100 + i for i in range(70)], symbol="AAA")}
    return replay(TEST_CONFIG, START, Decimal("100000"), bars, THROUGH)


@pytest.mark.integration
def test_replay_starts_at_capital_and_records_orders_then_fills():
    days = run_replay()
    assert (days[0].day, days[-1].day) == (START, THROUGH)
    assert abs(days[0].equity - Decimal("100000")) < 10  # only the start day's own interest
    assert [o["role"] for o in days[0].orders] == ["entry"]
    feb2 = next(d for d in days if d.day == date(2026, 2, 2))
    assert [f["role"] for f in feb2.fills] == ["entry"]
    assert feb2.positions.get("AAA", 0) > 0


@pytest.mark.integration
def test_replay_is_deterministic():
    first, second = run_replay(), run_replay()
    states = lambda days: [DayState(d.day, d.equity, d.positions) for d in days]
    assert find_drift(states(first), states(second)) == []
