from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MarketDataIngestRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    start: date
    end: date
    interval: str = "1d"


class MarketDataIngestResponse(BaseModel):
    symbol: str
    interval: str
    rows_fetched: int
    rows_inserted: int


class MarketBarResponse(BaseModel):
    symbol: str
    timestamp: datetime
    interval: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
