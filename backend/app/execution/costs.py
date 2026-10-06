from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.oms.states import OrderSide

TICK = Decimal("0.01")
BPS = Decimal("10000")


class CostModel(BaseModel):
    """Execution cost assumptions. Rounding always goes against the trader."""

    model_config = ConfigDict(frozen=True)

    commission_per_share: Decimal = Field(Decimal("0.005"), ge=0)
    min_commission: Decimal = Field(Decimal("1.00"), ge=0)
    slippage_bps: Decimal = Field(Decimal("5"), ge=0)
    max_volume_participation: Decimal = Field(Decimal("0.10"), gt=0, le=1)

    def commission(self, quantity: int) -> Decimal:
        per_share = (self.commission_per_share * quantity).quantize(TICK, rounding=ROUND_CEILING)
        return max(self.min_commission, per_share)

    def with_slippage(self, price: Decimal, side: OrderSide) -> Decimal:
        factor = self.slippage_bps / BPS
        if side == OrderSide.BUY:
            return (price * (1 + factor)).quantize(TICK, rounding=ROUND_CEILING)
        return (price * (1 - factor)).quantize(TICK, rounding=ROUND_FLOOR)
