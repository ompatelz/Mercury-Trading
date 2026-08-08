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
        return sample_raw_bars()


def sample_raw_bars() -> pl.DataFrame:
    closes = [100, 101, 102, 101, 103, 105, 104, 106, 108, 109]
    return pl.DataFrame(
        {
            "Date": [f"2024-01-{day:02d}" for day in range(1, 11)],
            "Open": closes,
            "High": [price + 1 for price in closes],
            "Low": [price - 1 for price in closes],
            "Close": closes,
            "Volume": [1_000 + day for day in range(10)],
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
