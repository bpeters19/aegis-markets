from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.engine.events import SignalAction, SignalEvent
from app.portfolio.snapshot import PortfolioSnapshot
from app.risk.limits import RiskLimits


class RiskStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class RiskDecision:
    status: RiskStatus
    signal: SignalEvent
    quantity: int
    notional: Decimal
    risk_amount: Decimal
    reasons: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def approved(self) -> bool:
        return self.status == RiskStatus.APPROVED


class RiskEngine:
    """Pre-trade risk checks and position sizing.

    evaluate() is a pure function of the signal and a portfolio snapshot:
    no I/O, no side effects. The kill switch is the only runtime state.
    """

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()
        self._halt_reason: str | None = None

    @property
    def halted(self) -> bool:
        return self._halt_reason is not None

    def halt(self, reason: str) -> None:
        self._halt_reason = reason

    def resume(self) -> None:
        self._halt_reason = None

    def evaluate(
        self,
        signal: SignalEvent,
        portfolio: PortfolioSnapshot,
        requested_quantity: int | None = None,
    ) -> RiskDecision:
        if signal.action == SignalAction.SELL:
            return self._evaluate_exit(signal, portfolio)
        return self._evaluate_entry(signal, portfolio, requested_quantity)

    def _evaluate_exit(self, signal: SignalEvent, portfolio: PortfolioSnapshot) -> RiskDecision:
        position = portfolio.positions.get(signal.symbol)
        if position is None or position.quantity <= 0:
            return RiskDecision(
                RiskStatus.REJECTED, signal, 0, Decimal(0), Decimal(0),
                reasons=("no open position to exit",),
            )
        notes = ("exit allowed while trading is halted (reduce-only)",) if self.halted else ()
        return RiskDecision(
            RiskStatus.APPROVED, signal, position.quantity,
            signal.price * position.quantity, Decimal(0), notes=notes,
        )

    def _evaluate_entry(
        self,
        signal: SignalEvent,
        portfolio: PortfolioSnapshot,
        requested_quantity: int | None,
    ) -> RiskDecision:
        limits = self.limits
        equity = portfolio.equity
        price = signal.price
        stop = signal.stop_loss
        reasons: list[str] = []
        notes: list[str] = []

        if equity <= 0:
            return RiskDecision(
                RiskStatus.REJECTED, signal, 0, Decimal(0), Decimal(0),
                reasons=("portfolio equity is not positive",),
            )
        if self.halted:
            reasons.append(f"trading halted: {self._halt_reason}")
        if stop is None:
            if limits.require_stop_loss:
                reasons.append("stop-loss required")
        elif stop >= price:
            reasons.append("stop-loss must be below entry for a long position")
        if signal.symbol in portfolio.positions:
            reasons.append(f"already holding {signal.symbol}")
        if len(portfolio.positions) >= limits.max_open_positions:
            reasons.append(f"max open positions reached ({limits.max_open_positions})")
        if portfolio.daily_pnl_pct <= -limits.max_daily_loss_pct:
            reasons.append(
                f"daily loss {portfolio.daily_pnl_pct:.2%} hit the {limits.max_daily_loss_pct:.0%} limit"
            )

        per_share_risk = price - stop if stop is not None and stop < price else None
        if requested_quantity is None:
            quantity = self._size(price, per_share_risk, portfolio, notes)
        else:
            quantity = requested_quantity

        notional = price * quantity
        risk_amount = per_share_risk * quantity if per_share_risk is not None else Decimal(0)

        if quantity < 1:
            reasons.append("position size rounds to zero shares")
        else:
            if notional > limits.max_position_pct * equity:
                reasons.append(
                    f"position is {notional / equity:.1%} of equity, limit is {limits.max_position_pct:.0%}"
                )
            if risk_amount > limits.max_risk_per_trade_pct * equity:
                reasons.append(
                    f"trade risks {risk_amount / equity:.2%} of equity, limit is {limits.max_risk_per_trade_pct:.0%}"
                )
            exposure_after = portfolio.gross_exposure + notional
            if exposure_after > limits.max_exposure_pct * equity:
                reasons.append(
                    f"exposure would be {exposure_after / equity:.1%}, limit is {limits.max_exposure_pct:.0%}"
                )
            if notional > portfolio.cash:
                reasons.append("insufficient buying power")

        status = RiskStatus.REJECTED if reasons else RiskStatus.APPROVED
        return RiskDecision(status, signal, quantity, notional, risk_amount, tuple(reasons), tuple(notes))

    def _size(
        self,
        price: Decimal,
        per_share_risk: Decimal | None,
        portfolio: PortfolioSnapshot,
        notes: list[str],
    ) -> int:
        limits = self.limits
        equity = portfolio.equity
        caps: dict[str, Decimal] = {}
        if per_share_risk is not None:
            caps["max risk per trade"] = (limits.max_risk_per_trade_pct * equity) // per_share_risk
        caps["max position size"] = (limits.max_position_pct * equity) // price
        caps["max total exposure"] = max(Decimal(0), limits.max_exposure_pct * equity - portfolio.gross_exposure) // price
        caps["buying power"] = max(Decimal(0), portfolio.cash) // price

        binding = min(caps, key=caps.__getitem__)
        notes.append(f"sized by {binding}")
        return int(caps[binding])
