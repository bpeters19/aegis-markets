from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.market_data.models import PRICE


class PaperAccount(Base):
    """A forward paper-trading account running one frozen strategy config from its start date."""

    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    hypothesis_id: Mapped[str] = mapped_column(String(16))
    config_hash: Mapped[str] = mapped_column(String(12))
    start_date: Mapped[date] = mapped_column(Date)
    capital: Mapped[Decimal] = mapped_column(PRICE)
    purpose: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaperDay(Base):
    """One trading day of a paper account. Append-only: a database trigger rejects UPDATE, DELETE and TRUNCATE."""

    __tablename__ = "paper_days"

    account_id: Mapped[int] = mapped_column(ForeignKey("paper_accounts.id"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    equity: Mapped[Decimal] = mapped_column(PRICE)
    cash: Mapped[Decimal] = mapped_column(PRICE)
    exposure: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    positions: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fills: Mapped[list[Any]] = mapped_column(JSONB)
    working_orders: Mapped[list[Any]] = mapped_column(JSONB)
    data_hash: Mapped[str] = mapped_column(String(12))
    code_commit: Mapped[str] = mapped_column(String(32))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
