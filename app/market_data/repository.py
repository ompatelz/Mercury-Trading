from datetime import date
from decimal import Decimal

import polars as pl
from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.market_data import MarketBar


class MarketDataRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_bars(self, bars: pl.DataFrame) -> int:
        payload = [
            {
                "symbol": row["symbol"],
                "timestamp": row["timestamp"],
                "interval": row["interval"],
                "open": Decimal(str(row["open"])),
                "high": Decimal(str(row["high"])),
                "low": Decimal(str(row["low"])),
                "close": Decimal(str(row["close"])),
                "volume": int(row["volume"]),
            }
            for row in bars.iter_rows(named=True)
        ]
        if not payload:
            return 0

        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            insert_stmt = pg_insert(MarketBar).values(payload)
            returning_stmt = insert_stmt.on_conflict_do_nothing(
                index_elements=["symbol", "timestamp", "interval"]
            ).returning(MarketBar.id)
            result = self.session.execute(returning_stmt)
            return len(result.scalars().all())

        inserted = 0
        for row in payload:
            exists = self.session.scalar(
                select(MarketBar.id).where(
                    MarketBar.symbol == row["symbol"],
                    MarketBar.timestamp == row["timestamp"],
                    MarketBar.interval == row["interval"],
                )
            )
            if exists is None:
                self.session.add(MarketBar(**row))
                inserted += 1
        return inserted

    def list_bars(
        self, symbol: str, interval: str, start: date | None, end: date | None
    ) -> list[MarketBar]:
        stmt: Select[tuple[MarketBar]] = select(MarketBar).where(
            MarketBar.symbol == symbol.upper(),
            MarketBar.interval == interval,
        )
        if start:
            stmt = stmt.where(MarketBar.timestamp >= start)
        if end:
            stmt = stmt.where(MarketBar.timestamp < end)
        stmt = stmt.order_by(MarketBar.timestamp)
        return list(self.session.scalars(stmt).all())
