from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class Timeframe(StrEnum):
    MINUTE_1 = "1Min"
    MINUTE_5 = "5Min"
    MINUTE_15 = "15Min"
    HOUR_1 = "1Hour"
    DAY_1 = "1Day"


class Bar(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: Timeframe
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("symbol is required")
        return value

    @field_validator("ts")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def check_ohlc(self) -> "Bar":
        if self.low <= 0:
            raise ValueError("prices must be positive")
        if self.high < self.low:
            raise ValueError("high is below low")
        if not (self.low <= self.open <= self.high):
            raise ValueError("open is outside the high/low range")
        if not (self.low <= self.close <= self.high):
            raise ValueError("close is outside the high/low range")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")
        return self
