from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RiskLimits(BaseModel):
    """Configurable pre-trade limits. Percentages are fractions of equity (0.10 = 10%)."""

    model_config = ConfigDict(frozen=True)

    max_position_pct: Decimal = Field(Decimal("0.10"), gt=0, le=1)
    max_exposure_pct: Decimal = Field(Decimal("0.70"), gt=0, le=1)
    max_risk_per_trade_pct: Decimal = Field(Decimal("0.01"), gt=0, le=1)
    max_daily_loss_pct: Decimal = Field(Decimal("0.03"), gt=0, le=1)
    max_open_positions: int = Field(5, ge=1)
    require_stop_loss: bool = True

    sizing_mode: Literal["stop", "volatility"] = "stop"
    target_position_volatility: Decimal = Field(Decimal("0.02"), gt=0, le=1)
