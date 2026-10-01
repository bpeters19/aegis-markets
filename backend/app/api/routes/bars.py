from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.market_data.domain import Timeframe
from app.market_data.repository import fetch_bars

router = APIRouter(prefix="/bars", tags=["market-data"])


class BarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    timeframe: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str


@router.get("", response_model=list[BarOut])
def list_bars(
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    limit: int = Query(1000, ge=1, le=10000),
    session: Session = Depends(get_session),
):
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(422, "start and end need a timezone, e.g. 2026-01-01T00:00:00Z")
    if start >= end:
        raise HTTPException(422, "start must be before end")
    return fetch_bars(session, symbol, timeframe, start, end, limit)
