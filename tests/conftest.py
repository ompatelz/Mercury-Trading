from collections.abc import Generator
from datetime import date

import polars as pl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_market_data_provider
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app


class StubMarketDataProvider:
    def fetch_bars(self, symbol: str, start: date, end: date, interval: str) -> pl.DataFrame:
        return sample_raw_bars(start=start, end=end)


def sample_raw_bars(start: date = date(2024, 1, 1), end: date = date(2024, 1, 11)) -> pl.DataFrame:
    days = max(0, (end - start).days)
    closes = [100 + day + ((day % 4) - 1) for day in range(days)]
    return pl.DataFrame(
        {
            "Date": [start.fromordinal(start.toordinal() + day).isoformat() for day in range(days)],
            "Open": closes,
            "High": [price + 1 for price in closes],
            "Low": [price - 1 for price in closes],
            "Close": closes,
            "Volume": [1_000 + day for day in range(days)],
        }
    )


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        yield session


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_market_data_provider] = lambda: StubMarketDataProvider()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
