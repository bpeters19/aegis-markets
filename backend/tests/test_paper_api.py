from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.session import get_engine, get_session
from app.main import app
from app.paper.accounts import create_account
from app.paper.models import PaperDay

pytestmark = pytest.mark.integration


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


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def add_day(session, account, day, equity, positions, fills=()):
    session.add(PaperDay(
        account_id=account.id, day=day, equity=Decimal(equity), cash=Decimal("50000"), exposure=Decimal("0.5"),
        positions=positions, fills=list(fills), working_orders=[], data_hash="test", code_commit="test",
    ))


def test_lists_accounts_with_their_latest_day(session, client):
    account = create_account(session, "test-api", "H1", Decimal("100000"), "api test", start=date(2026, 10, 12))
    add_day(session, account, date(2026, 10, 12), "100000", {})
    add_day(session, account, date(2026, 10, 13), "100500", {"SPY": 10})
    session.flush()

    row = next(a for a in client.get("/api/v1/paper/accounts").json() if a["name"] == "test-api")
    assert row["days_recorded"] == 2
    assert row["latest_day"] == "2026-10-13"
    assert row["latest_equity"] == "100500.00"
    assert row["return_since_start"] == pytest.approx(0.005)
    assert row["open_positions"] == 1


def test_account_detail_returns_the_ledger_in_order(session, client):
    account = create_account(session, "test-detail", "H3", Decimal("100000"), "api test", start=date(2026, 10, 12))
    fill = {"symbol": "SPY", "side": "BUY", "role": "entry", "quantity": 10, "price": "680.50"}
    add_day(session, account, date(2026, 10, 13), "100100", {"SPY": 10}, [fill])
    add_day(session, account, date(2026, 10, 12), "100000", {})
    session.flush()

    body = client.get("/api/v1/paper/accounts/test-detail").json()
    assert [d["day"] for d in body["days"]] == ["2026-10-12", "2026-10-13"]
    assert body["days"][1]["fills"] == [fill]


def test_unknown_account_is_404(client):
    assert client.get("/api/v1/paper/accounts/does-not-exist").status_code == 404
