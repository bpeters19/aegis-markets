from datetime import datetime, timezone
from decimal import Decimal

from app.engine.events import SignalAction, SignalEvent
from app.portfolio.snapshot import PortfolioSnapshot, Position
from app.risk.engine import RiskEngine, RiskStatus

TS = datetime(2026, 1, 2, tzinfo=timezone.utc)


def buy(symbol="NVDA", price="100", stop="95"):
    return SignalEvent(
        ts=TS, symbol=symbol, strategy_id="test", action=SignalAction.BUY,
        price=Decimal(price), stop_loss=Decimal(stop) if stop else None,
    )


def sell(symbol="NVDA", price="100"):
    return SignalEvent(ts=TS, symbol=symbol, strategy_id="test", action=SignalAction.SELL, price=Decimal(price))


def holding(symbol, qty, price):
    return Position(symbol, qty, Decimal(price), Decimal(price))


def portfolio(cash="100000", positions=(), sod=None):
    held = {p.symbol: p for p in positions}
    equity = Decimal(cash) + sum((p.market_value for p in held.values()), Decimal(0))
    return PortfolioSnapshot(Decimal(cash), held, Decimal(sod) if sod else equity)


def test_rejects_20_percent_nvda_position_from_spec():
    decision = RiskEngine().evaluate(buy(price="200", stop="190"), portfolio(), requested_quantity=100)
    assert decision.status == RiskStatus.REJECTED
    assert decision.reasons == ("position is 20.0% of equity, limit is 10%",)


def test_sizes_down_to_max_position():
    decision = RiskEngine().evaluate(buy(price="100", stop="95"), portfolio())
    assert decision.approved
    assert decision.quantity == 100
    assert decision.notional == Decimal("10000")
    assert decision.risk_amount == Decimal("500")
    assert decision.notes == ("sized by max position size",)


def test_sizes_by_risk_when_stop_is_wide():
    decision = RiskEngine().evaluate(buy(price="100", stop="80"), portfolio())
    assert decision.approved
    assert decision.quantity == 50
    assert decision.risk_amount == Decimal("1000")
    assert decision.notes == ("sized by max risk per trade",)


def test_requires_stop_loss():
    decision = RiskEngine().evaluate(buy(stop=None), portfolio())
    assert not decision.approved
    assert "stop-loss required" in decision.reasons


def test_rejects_duplicate_position():
    decision = RiskEngine().evaluate(buy("NVDA"), portfolio("90000", [holding("NVDA", 100, "100")]))
    assert "already holding NVDA" in decision.reasons


def test_rejects_when_max_open_positions_reached():
    held = [holding(s, 10, "100") for s in ("AAA", "BBB", "CCC", "DDD", "EEE")]
    decision = RiskEngine().evaluate(buy("AAPL"), portfolio("95000", held))
    assert any("max open positions" in r for r in decision.reasons)


def test_daily_loss_limit_blocks_new_entries():
    decision = RiskEngine().evaluate(buy(), portfolio(cash="96000", sod="100000"))
    assert any("daily loss" in r for r in decision.reasons)


def test_rejects_requested_size_over_exposure_limit():
    held = [holding(s, 162, "100") for s in ("AAA", "BBB", "CCC", "DDD")]
    decision = RiskEngine().evaluate(buy(), portfolio("35200", held), requested_quantity=100)
    assert decision.reasons == ("exposure would be 74.8%, limit is 70%",)


def test_sizes_down_to_remaining_exposure():
    held = [holding(s, 162, "100") for s in ("AAA", "BBB", "CCC", "DDD")]
    decision = RiskEngine().evaluate(buy(), portfolio("35200", held))
    assert decision.approved
    assert decision.quantity == 52
    assert decision.notes == ("sized by max total exposure",)


def test_kill_switch_blocks_entries_but_allows_exits():
    engine = RiskEngine()
    book = portfolio("90000", [holding("NVDA", 100, "100")])
    engine.halt("manual stop")

    entry = engine.evaluate(buy("AAPL"), book)
    exit_ = engine.evaluate(sell("NVDA"), book)
    assert "trading halted: manual stop" in entry.reasons
    assert exit_.approved and exit_.quantity == 100
    assert any("reduce-only" in n for n in exit_.notes)

    engine.resume()
    assert engine.evaluate(buy("AAPL"), book).approved


def test_sell_without_position_rejected():
    decision = RiskEngine().evaluate(sell("AMZN"), portfolio())
    assert decision.reasons == ("no open position to exit",)


def test_collects_every_failed_check():
    engine = RiskEngine()
    engine.halt("manual stop")
    decision = engine.evaluate(buy("NVDA", stop=None), portfolio("90000", [holding("NVDA", 100, "100")]))
    assert len(decision.reasons) >= 3
