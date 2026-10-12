from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.paper.accounts import create_account
from app.paper.ledger import DayState, find_drift, unrecorded_days
from app.paper.models import PaperDay
from app.research.config import config_hash
from app.research.hypotheses.h1 import H1

D1, D2, D3 = date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)


def state(day, equity="100000.00", positions=None):
    return DayState(day, Decimal(equity), positions or {})


def test_matching_replay_has_no_drift():
    days = [state(D1), state(D2, "100250.00", {"SPY": 10})]
    assert find_drift(days, list(days)) == []


def test_equity_difference_is_drift():
    issues = find_drift([state(D1, "100000.00")], [state(D1, "100000.50")])
    assert issues and issues[0][0] == D1


def test_rounding_noise_is_not_drift():
    assert find_drift([state(D1, "100000.00")], [state(D1, "100000.004")]) == []


def test_position_difference_is_drift():
    issues = find_drift([state(D1, positions={"SPY": 10})], [state(D1, positions={"SPY": 11})])
    assert "positions" in issues[0][1]


def test_missing_day_is_drift():
    assert find_drift([state(D1), state(D2)], [state(D1)])[0] == (D2, "recorded day is missing from the replay")


def test_only_days_after_the_last_recorded_one_are_new():
    assert unrecorded_days([state(D1), state(D2)], [state(D1), state(D2), state(D3)]) == [state(D3)]
    assert unrecorded_days([], [state(D1)]) == [state(D1)]


@pytest.fixture
def session():
    connection = get_engine().connect()
    transaction = connection.begin()
    s = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        transaction.rollback()
        connection.close()


@pytest.mark.integration
def test_account_records_the_strategy_config_hash(session):
    account = create_account(session, "test-account", "H1", Decimal("100000"), "unit test", start=D1)
    assert account.config_hash == config_hash(H1)
    with pytest.raises(ValueError):
        create_account(session, "test-h2", "H2", Decimal("100000"), "portfolios are not supported yet")


@pytest.mark.integration
def test_paper_days_are_append_only(session):
    account = create_account(session, "test-ledger", "H1", Decimal("100000"), "unit test", start=D1)
    session.add(PaperDay(
        account_id=account.id, day=D1, equity=Decimal("100000"), cash=Decimal("100000"), exposure=Decimal("0"),
        positions={}, fills=[], working_orders=[], data_hash="test", code_commit="test",
    ))
    session.flush()
    for sql in ("UPDATE paper_days SET equity = 1 WHERE account_id = :id",
                "DELETE FROM paper_days WHERE account_id = :id"):
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(text(sql), {"id": account.id})
