from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.paper.models import PaperAccount, PaperDay

router = APIRouter(prefix="/paper", tags=["paper-trading"])
CENT = Decimal("0.01")


class PaperDayOut(BaseModel):
    day: date
    equity: Decimal
    cash: Decimal
    exposure: float
    positions: dict[str, int]
    fills: list[dict[str, Any]]
    working_orders: list[dict[str, Any]]
    data_hash: str
    code_commit: str


class PaperAccountSummary(BaseModel):
    name: str
    hypothesis_id: str
    config_hash: str
    start_date: date
    capital: Decimal
    purpose: str
    days_recorded: int
    latest_day: date | None
    latest_equity: Decimal | None
    return_since_start: float | None
    open_positions: int


class PaperAccountDetail(PaperAccountSummary):
    days: list[PaperDayOut]


def _summary(account: PaperAccount, days_recorded: int, latest: PaperDay | None) -> PaperAccountSummary:
    return PaperAccountSummary(
        name=account.name,
        hypothesis_id=account.hypothesis_id,
        config_hash=account.config_hash,
        start_date=account.start_date,
        capital=account.capital.quantize(CENT),
        purpose=account.purpose,
        days_recorded=days_recorded,
        latest_day=latest.day if latest else None,
        latest_equity=latest.equity.quantize(CENT) if latest else None,
        return_since_start=float(latest.equity / account.capital - 1) if latest else None,
        open_positions=len(latest.positions) if latest else 0,
    )


def _day(d: PaperDay) -> PaperDayOut:
    return PaperDayOut(
        day=d.day, equity=d.equity.quantize(CENT), cash=d.cash.quantize(CENT), exposure=float(d.exposure),
        positions=dict(d.positions), fills=list(d.fills), working_orders=list(d.working_orders),
        data_hash=d.data_hash, code_commit=d.code_commit,
    )


@router.get("/accounts", response_model=list[PaperAccountSummary])
def list_accounts(session: Session = Depends(get_session)) -> list[PaperAccountSummary]:
    summaries = []
    for account in session.scalars(select(PaperAccount).order_by(PaperAccount.id)):
        count = session.scalar(select(func.count()).select_from(PaperDay).where(PaperDay.account_id == account.id))
        latest = session.scalars(
            select(PaperDay).where(PaperDay.account_id == account.id).order_by(PaperDay.day.desc()).limit(1)
        ).first()
        summaries.append(_summary(account, count or 0, latest))
    return summaries


@router.get("/accounts/{name}", response_model=PaperAccountDetail)
def account_detail(name: str, session: Session = Depends(get_session)) -> PaperAccountDetail:
    account = session.scalar(select(PaperAccount).where(PaperAccount.name == name))
    if account is None:
        raise HTTPException(404, f"No paper account named {name}")
    days = list(session.scalars(select(PaperDay).where(PaperDay.account_id == account.id).order_by(PaperDay.day)))
    summary = _summary(account, len(days), days[-1] if days else None)
    return PaperAccountDetail(**summary.model_dump(), days=[_day(d) for d in days])
