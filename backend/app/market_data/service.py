import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.market_data.domain import Timeframe
from app.market_data.providers.base import MarketDataProvider
from app.market_data.repository import upsert_bars

logger = logging.getLogger(__name__)


def ingest_bars(
    session: Session,
    provider: MarketDataProvider,
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> int:
    bars = provider.get_bars(symbol, timeframe, start, end)
    count = upsert_bars(session, bars, source=provider.name)
    session.commit()
    logger.info("Ingested %d %s bars for %s from %s", count, timeframe, symbol, provider.name)
    return count
