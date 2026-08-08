from datetime import date

from sqlalchemy.orm import Session

from app.market_data.normalization import normalize_bars
from app.market_data.provider import MarketDataProvider
from app.market_data.repository import MarketDataRepository
from app.models.market_data import MarketBar


class MarketDataService:
    def __init__(self, session: Session, provider: MarketDataProvider) -> None:
        self.repository = MarketDataRepository(session)
        self.provider = provider

    def ingest(self, symbol: str, start: date, end: date, interval: str) -> tuple[int, int]:
        raw = self.provider.fetch_bars(symbol=symbol, start=start, end=end, interval=interval)
        normalized = normalize_bars(raw, symbol=symbol, interval=interval)
        inserted = self.repository.upsert_bars(normalized)
        return normalized.height, inserted

    def list_bars(
        self, symbol: str, interval: str = "1d", start: date | None = None, end: date | None = None
    ) -> list[MarketBar]:
        return self.repository.list_bars(symbol=symbol, interval=interval, start=start, end=end)
