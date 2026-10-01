from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.market_data.domain import Bar, Timeframe
from app.market_data.models import BarRecord

BATCH_SIZE = 1000
UPDATABLE = ("open", "high", "low", "close", "volume", "source")


def upsert_bars(session: Session, bars: list[Bar], source: str) -> int:
    rows = [
        {**bar.model_dump(), "timeframe": bar.timeframe.value, "source": source}
        for bar in bars
    ]
    for i in range(0, len(rows), BATCH_SIZE):
        stmt = insert(BarRecord).values(rows[i : i + BATCH_SIZE])
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "ts"],
            set_={**{col: stmt.excluded[col] for col in UPDATABLE}, "ingested_at": func.now()},
        )
        session.execute(stmt)
    return len(rows)


def fetch_bars(
    session: Session,
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    limit: int,
) -> list[BarRecord]:
    stmt = (
        select(BarRecord)
        .where(
            BarRecord.symbol == symbol.strip().upper(),
            BarRecord.timeframe == timeframe.value,
            BarRecord.ts >= start,
            BarRecord.ts < end,
        )
        .order_by(BarRecord.ts)
        .limit(limit)
    )
    return list(session.scalars(stmt))
