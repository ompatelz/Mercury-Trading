from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.market_data.live import (
    LiveMarketBar,
    StaticLiveMarketDataProvider,
    live_bar_from_mapping,
)
from app.market_data.normalization import MarketDataValidationError
from app.models.market_data import MarketBar
from app.paper_trading.clock import MarketClock, MarketSessionState
from app.paper_trading.live_service import LivePaperTradingService
from app.paper_trading.schemas import LivePaperTradingSessionCreateRequest


def test_live_bar_normalization_rejects_malformed_events() -> None:
    with pytest.raises(MarketDataValidationError, match="OHLC"):
        live_bar_from_mapping(
            {
                "Datetime": datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
                "Open": 100,
                "High": 99,
                "Low": 98,
                "Close": 100,
                "Volume": 1_000,
            },
            symbol="MSFT",
            interval="1m",
            source="test",
        )


def test_market_clock_tracks_open_pre_market_and_closed() -> None:
    clock = MarketClock()

    assert clock.state_at(datetime(2024, 1, 2, 12, 0, tzinfo=UTC)) == MarketSessionState.PRE_MARKET
    assert clock.state_at(datetime(2024, 1, 2, 14, 0, tzinfo=UTC)) == MarketSessionState.OPEN
    assert clock.state_at(datetime(2024, 1, 6, 14, 0, tzinfo=UTC)) == MarketSessionState.CLOSED


def test_live_session_warms_up_and_executes_paper_pipeline(db_session: Session) -> None:
    db_session.add_all(_stored_bars([100, 101, 102]))
    db_session.commit()
    service = _service(db_session, _live_bars([103, 104, 98, 97]))

    result = service.create_session(
        LivePaperTradingSessionCreateRequest(
            symbol="MSFT",
            interval="1m",
            strategy_parameters={"fast_window": 2, "slow_window": 3},
            warmup_start=datetime(2024, 1, 1, tzinfo=UTC).date(),
            warmup_end=datetime(2024, 1, 4, tzinfo=UTC).date(),
            max_events=4,
            initial_cash=10_000,
            commission_bps=1,
        )
    )

    assert result.status == "STOPPED"
    assert result.metrics["market_events_received"] == 4
    assert result.metrics["signals_generated"] == 4
    assert result.metrics["fills"] >= 1
    assert result.metrics["processing_latency"]["total_pipeline_ms"] >= 0
    assert result.final_portfolio["equity"] > 0


def test_live_session_records_reconnect_without_crashing(db_session: Session) -> None:
    db_session.add_all(_stored_bars([100, 101, 102]))
    db_session.commit()
    provider = StaticLiveMarketDataProvider(_live_bars([103, 104]), fail_after=1)
    service = _service(db_session, [], provider=provider)

    result = service.create_session(
        LivePaperTradingSessionCreateRequest(
            symbol="MSFT",
            interval="1m",
            strategy_parameters={"fast_window": 2, "slow_window": 3},
            warmup_start=datetime(2024, 1, 1, tzinfo=UTC).date(),
            warmup_end=datetime(2024, 1, 4, tzinfo=UTC).date(),
            max_events=2,
            max_reconnect_attempts=2,
            reconnect_backoff_seconds=0,
        )
    )

    assert result.status == "STOPPED"
    assert result.metrics["feed_disconnects"] == 1
    assert result.metrics["market_events_received"] == 2


def test_live_session_rejects_out_of_order_market_events(db_session: Session) -> None:
    db_session.add_all(_stored_bars([100, 101, 102]))
    db_session.commit()
    bars = _live_bars([103, 104])
    provider = StaticLiveMarketDataProvider([bars[1], bars[0]])
    service = _service(db_session, [], provider=provider)

    result = service.create_session(
        LivePaperTradingSessionCreateRequest(
            symbol="MSFT",
            interval="1m",
            strategy_parameters={"fast_window": 2, "slow_window": 3},
            warmup_start=datetime(2024, 1, 1, tzinfo=UTC).date(),
            warmup_end=datetime(2024, 1, 4, tzinfo=UTC).date(),
            max_events=2,
        )
    )

    assert result.metrics["market_events_received"] == 1
    assert result.metrics["malformed_events"] == 1


def _service(
    db_session: Session,
    bars: list[LiveMarketBar],
    *,
    provider: StaticLiveMarketDataProvider | None = None,
) -> LivePaperTradingService:
    factory = sessionmaker(
        bind=db_session.bind,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return LivePaperTradingService(
        factory,
        provider or StaticLiveMarketDataProvider(bars),
    )


def _stored_bars(closes: list[float]) -> list[MarketBar]:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        MarketBar(
            symbol="MSFT",
            timestamp=start + timedelta(days=index),
            interval="1m",
            open=Decimal(str(close)),
            high=Decimal(str(close + 1)),
            low=Decimal(str(close - 1)),
            close=Decimal(str(close)),
            volume=1_000 + index,
        )
        for index, close in enumerate(closes)
    ]


def _live_bars(closes: list[float]) -> list[LiveMarketBar]:
    return [
        live_bar_from_mapping(
            {
                "Datetime": datetime(2024, 1, 2, 14, 30 + index, tzinfo=UTC),
                "Open": close,
                "High": close + 1,
                "Low": close - 1,
                "Close": close,
                "Volume": 1_000 + index,
            },
            symbol="MSFT",
            interval="1m",
            source="test",
        )
        for index, close in enumerate(closes)
    ]
