from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.market_data import MarketBar
from app.paper_trading.broker import PaperBroker
from app.paper_trading.events import MarketEvent, OrderEvent, OrderSide, OrderStatus, new_id
from app.paper_trading.execution import ExecutionConfig, ExecutionModelName
from app.paper_trading.portfolio import Portfolio
from app.paper_trading.risk import RiskConfig, RiskEngine
from app.paper_trading.schemas import PaperTradingSessionCreateRequest
from app.paper_trading.service import PaperTradingService
from app.paper_trading.strategy import MovingAverageSignalStrategy
from app.paper_trading.stream import HistoricalReplayStream


def test_historical_replay_orders_events_chronologically() -> None:
    session_id = uuid4()
    bars = _bars([104, 100, 102])

    events = list(HistoricalReplayStream(session_id=session_id, bars=bars).events())

    assert [event.sequence for event in events] == [1, 2, 3]
    assert [event.timestamp for event in events] == sorted(event.timestamp for event in events)
    assert [event.close for event in events] == [104.0, 100.0, 102.0]


def test_strategy_uses_prior_bars_before_current_market_event() -> None:
    session_id = uuid4()
    portfolio = Portfolio(10_000)
    strategy = MovingAverageSignalStrategy(
        fast_window=2,
        slow_window=3,
        target_exposure_pct=0.5,
    )
    events = list(
        HistoricalReplayStream(session_id=session_id, bars=_bars([100, 101, 102, 103])).events()
    )

    for event in events[:3]:
        signal = strategy.on_market(event, portfolio)
        assert signal.reason == "warming up"
        strategy.observe(event)

    signal = strategy.on_market(events[3], portfolio)

    assert signal.direction == "BUY"
    assert signal.metadata["last_history_timestamp"] == events[2].timestamp.isoformat()
    assert signal.metadata["history_bars"] == 3


def test_risk_rejects_invalid_duplicate_and_cash_limited_orders() -> None:
    portfolio = Portfolio(100)
    risk = RiskEngine(RiskConfig(max_position_quantity=10, max_order_value=1_000))
    order = _order(quantity=1)

    submitted = risk.check(order, portfolio, 10)
    duplicate = risk.check(order, portfolio, 10)
    invalid = risk.check(_order(quantity=0), portfolio, 10)
    too_expensive = risk.check(_order(quantity=20), portfolio, 10)

    assert submitted.status == OrderStatus.SUBMITTED
    assert duplicate.status == OrderStatus.REJECTED
    assert duplicate.reason == "duplicate order"
    assert invalid.reason == "invalid quantity"
    assert too_expensive.reason == "maximum position size exceeded"


def test_paper_broker_applies_commission_and_slippage_to_market_fill() -> None:
    order = _order(quantity=10, status=OrderStatus.SUBMITTED)
    fill = PaperBroker(commission_bps=10, slippage_bps=50).submit_order(order, 100)

    assert fill.price == 100.5
    assert fill.gross_notional == 1005.0
    assert fill.fees == 1.005
    assert fill.slippage_cost == 5.0


def test_portfolio_updates_from_fill_events_only() -> None:
    portfolio = Portfolio(2_000)
    buy = PaperBroker(commission_bps=0, slippage_bps=0).submit_order(
        _order(quantity=10, status=OrderStatus.SUBMITTED),
        100,
    )
    portfolio.apply_fill(buy)
    portfolio.mark_price("MSFT", 110)

    sell_order = _order(quantity=4, side=OrderSide.SELL, status=OrderStatus.SUBMITTED)
    sell = PaperBroker(commission_bps=0, slippage_bps=0).submit_order(sell_order, 110)
    portfolio.apply_fill(sell)

    assert portfolio.cash == 1_440
    assert portfolio.position_quantity("MSFT") == 6
    assert portfolio.realized_pnl == 40
    assert portfolio.equity() == 2_100


def test_quote_execution_uses_ask_for_buys_and_bid_for_sells() -> None:
    broker = PaperBroker(
        commission_bps=0,
        slippage_bps=0,
        execution_config=ExecutionConfig(model=ExecutionModelName.BASIC_SLIPPAGE),
    )
    market = _market_event(bid=99, ask=101, volume=1_000)

    buy = broker.execute(_order(quantity=1, status=OrderStatus.SUBMITTED), market)
    sell = broker.execute(
        _order(quantity=1, side=OrderSide.SELL, status=OrderStatus.SUBMITTED), market
    )

    assert buy.fills[0].price == 101
    assert sell.fills[0].price == 99


def test_microstructure_execution_partially_fills_and_tracks_average_price() -> None:
    broker = PaperBroker(
        commission_bps=0,
        slippage_bps=0,
        execution_config=ExecutionConfig(
            model=ExecutionModelName.MICROSTRUCTURE,
            max_participation_rate=0.5,
        ),
    )
    order = _order(quantity=10, status=OrderStatus.SUBMITTED)

    first = broker.execute(order, _market_event(bid=99, ask=101, volume=6))
    second = broker.execute(first.order, _market_event(bid=101, ask=103, volume=20))

    assert first.order.status == OrderStatus.PARTIALLY_FILLED
    assert first.order.filled_quantity == 3
    assert second.order.status == OrderStatus.FILLED
    assert second.order.filled_quantity == 10
    assert second.order.average_fill_price > 101


def test_larger_participation_has_greater_market_impact() -> None:
    broker = PaperBroker(
        commission_bps=0,
        slippage_bps=0,
        execution_config=ExecutionConfig(
            model=ExecutionModelName.MICROSTRUCTURE,
            impact_coefficient_bps=100,
        ),
    )
    market = _market_event(bid=99, ask=101, volume=100)

    small = broker.execute(_order(quantity=1, status=OrderStatus.SUBMITTED), market)
    large = broker.execute(_order(quantity=81, status=OrderStatus.SUBMITTED), market)

    assert large.fills[0].impact_cost > small.fills[0].impact_cost


def test_end_to_end_paper_session_persists_orders_fills_and_portfolio(
    db_session: Session,
) -> None:
    db_session.add_all(_bars([100, 101, 102, 103, 99, 98], symbol="MSFT"))
    db_session.commit()

    result = PaperTradingService(db_session).create_session(
        PaperTradingSessionCreateRequest(
            symbol="MSFT",
            start=datetime(2024, 1, 1, tzinfo=UTC).date(),
            end=datetime(2024, 1, 7, tzinfo=UTC).date(),
            strategy_parameters={"fast_window": 2, "slow_window": 3},
            initial_cash=10_000,
            commission_bps=1,
            slippage_bps=0,
        )
    )

    assert result.status == "completed"
    assert result.metrics["market_events"] == 6
    assert result.metrics["fills"] == 2
    assert result.metrics["ending_equity"] > 0
    assert len(result.orders) == 2
    assert len(result.fills) == 2
    assert result.events[0].event_type == "SESSION"
    assert result.events[-1].payload["status"] == "completed"


def test_latency_uses_a_future_replay_event_without_lookahead(db_session: Session) -> None:
    db_session.add_all(_bars([100, 101, 102, 103, 99, 98], symbol="MSFT"))
    db_session.commit()

    result = PaperTradingService(db_session).create_session(
        PaperTradingSessionCreateRequest(
            symbol="MSFT",
            start=datetime(2024, 1, 1, tzinfo=UTC).date(),
            end=datetime(2024, 1, 7, tzinfo=UTC).date(),
            strategy_parameters={"fast_window": 2, "slow_window": 3},
            latency_bars=1,
        )
    )

    assert result.fills
    assert result.fills[0].timestamp > result.orders[0].created_at
    assert result.metrics["execution"]["latency_bars"] == 1


def _order(
    *,
    quantity: float,
    side: OrderSide = OrderSide.BUY,
    status: OrderStatus = OrderStatus.CREATED,
) -> OrderEvent:
    return OrderEvent(
        session_id=uuid4(),
        order_id=new_id(),
        strategy_id="moving_average_crossover",
        symbol="MSFT",
        side=side,
        quantity=quantity,
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
        status=status,
    )


def _bars(closes: list[float], *, symbol: str = "MSFT") -> list[MarketBar]:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        MarketBar(
            symbol=symbol,
            timestamp=start + timedelta(days=index),
            interval="1d",
            open=Decimal(str(close)),
            high=Decimal(str(close + 1)),
            low=Decimal(str(close - 1)),
            close=Decimal(str(close)),
            volume=1_000 + index,
        )
        for index, close in reversed(list(enumerate(closes)))
    ]


def _market_event(*, bid: float, ask: float, volume: int) -> MarketEvent:
    return MarketEvent(
        session_id=uuid4(),
        timestamp=datetime(2024, 1, 2, tzinfo=UTC),
        symbol="MSFT",
        interval="1d",
        open=100,
        high=101,
        low=99,
        close=100,
        volume=volume,
        sequence=1,
        bid=bid,
        ask=ask,
    )
