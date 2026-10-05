import argparse
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_engine
from app.market_data.domain import Timeframe
from app.market_data.providers.alpaca import AlpacaProvider
from app.market_data.providers.fake import FakeProvider
from app.market_data.providers.tiingo import TiingoProvider
from app.market_data.service import ingest_bars

PROVIDERS = {
    "fake": lambda: FakeProvider(),
    "alpaca": lambda: AlpacaProvider.from_settings(get_settings()),
    "tiingo": lambda: TiingoProvider.from_settings(get_settings()),
}


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest market data bars")
    parser.add_argument("--provider", choices=PROVIDERS, default="fake")
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--timeframe", type=Timeframe, default=Timeframe.DAY_1)
    parser.add_argument("--start", type=parse_utc, required=True, help="ISO date; UTC if no offset")
    parser.add_argument("--end", type=parse_utc, required=True, help="ISO date; UTC if no offset")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    provider = PROVIDERS[args.provider]()
    total = 0
    with Session(get_engine()) as session:
        for symbol in args.symbols:
            count = ingest_bars(session, provider, symbol, args.timeframe, args.start, args.end)
            print(f"{symbol.upper():<8} {count:>7} bars")
            total += count
    print(f"Done: {total} bars across {len(args.symbols)} symbols from {provider.name}")


if __name__ == "__main__":
    main()
