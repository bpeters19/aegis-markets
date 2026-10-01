from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

PRICE = Numeric(18, 6)
VOLUME = Numeric(24, 8)


class BarRecord(Base):
    __tablename__ = "bars"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(PRICE)
    high: Mapped[Decimal] = mapped_column(PRICE)
    low: Mapped[Decimal] = mapped_column(PRICE)
    close: Mapped[Decimal] = mapped_column(PRICE)
    volume: Mapped[Decimal] = mapped_column(VOLUME)
    source: Mapped[str] = mapped_column(String(32))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("low > 0", name="low_positive"),
        CheckConstraint("high >= low", name="high_gte_low"),
        CheckConstraint("open BETWEEN low AND high", name="open_in_range"),
        CheckConstraint("close BETWEEN low AND high", name="close_in_range"),
        CheckConstraint("volume >= 0", name="volume_non_negative"),
    )
