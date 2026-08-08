from sqlalchemy.orm import Session

from app.market_data.normalization import normalize_bars
from app.market_data.repository import MarketDataRepository
from tests.conftest import sample_raw_bars


def test_upsert_bars_ignores_duplicates(db_session: Session) -> None:
    repository = MarketDataRepository(db_session)
    bars = normalize_bars(sample_raw_bars(), symbol="MSFT", interval="1d")

    first_count = repository.upsert_bars(bars)
    second_count = repository.upsert_bars(bars)
    db_session.commit()

    assert first_count == 10
    assert second_count == 0
    assert len(repository.list_bars("MSFT", "1d", None, None)) == 10
