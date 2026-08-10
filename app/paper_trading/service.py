import time
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.backtesting.registry import validate_strategy_spec
from app.market_data.repository import MarketDataRepository
from app.models.paper_trading import (
    PaperFillRecord,
    PaperOrderRecord,
    PaperTraceEventRecord,
    PaperTradingSession,
)
from app.paper_trading.broker import PaperBroker
from app.paper_trading.events import (
    EventType,
    FillEvent,
    OrderEvent,
    OrderSide,
    OrderStatus,
    SignalDirection,
    new_id,
)
from app.paper_trading.portfolio import Portfolio
from app.paper_trading.risk import RiskConfig, RiskEngine
from app.paper_trading.schemas import PaperTradingSessionCreateRequest
from app.paper_trading.strategy import MovingAverageSignalStrategy
from app.paper_trading.stream import HistoricalReplayStream


class PaperTradingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.market_data = MarketDataRepository(session)

    def create_session(self, request: PaperTradingSessionCreateRequest) -> PaperTradingSession:
        validated = validate_strategy_spec(request.strategy_name, request.strategy_parameters)
        bars = self.market_data.list_bars(
            symbol=request.symbol,
            interval=request.interval,
            start=request.start,
            end=request.end,
        )
        if not bars:
            raise ValueError("no market bars found; ingest market data before paper trading")

        risk_config = RiskConfig(
            max_position_quantity=request.max_position_quantity,
            max_order_value=request.max_order_value,
            max_gross_exposure_pct=request.max_gross_exposure_pct,
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
        )
        paper_session = PaperTradingSession(
            strategy_name=request.strategy_name,
            strategy_parameters=validated,
            symbol=request.symbol.upper(),
            interval=request.interval,
            start_date=request.start,
            end_date=request.end,
            execution_mode=request.execution_mode.value,
            status="running",
            initial_cash=Decimal(str(request.initial_cash)),
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
            risk_config=asdict(risk_config),
            metrics={},
            final_portfolio={},
            error_message=None,
        )
        self.session.add(paper_session)
        self.session.flush()

        started = time.perf_counter()
        sequence = 0
        portfolio = Portfolio(request.initial_cash)
        broker = PaperBroker(
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
        )
        risk = RiskEngine(risk_config)
        strategy = MovingAverageSignalStrategy(
            fast_window=validated["fast_window"],
            slow_window=validated["slow_window"],
            target_exposure_pct=request.target_exposure_pct,
        )
        market_events = 0
        signal_events = 0
        rejected_orders = 0
        filled_orders = 0
        try:
            sequence = self._record_event(
                paper_session.id,
                sequence,
                EventType.SESSION,
                None,
                {"status": "started", "execution_mode": request.execution_mode.value},
            )
            stream = HistoricalReplayStream(session_id=paper_session.id, bars=bars)
            for market_event in stream.events():
                market_events += 1
                sequence = self._record_event(
                    paper_session.id,
                    sequence,
                    EventType.MARKET,
                    market_event.timestamp,
                    _event_payload(market_event),
                )
                portfolio.mark_price(market_event.symbol, market_event.open)
                signal = strategy.on_market(market_event, portfolio)
                signal_events += 1
                sequence = self._record_event(
                    paper_session.id,
                    sequence,
                    EventType.SIGNAL,
                    signal.timestamp,
                    _event_payload(signal),
                )

                if signal.direction in {
                    SignalDirection.BUY,
                    SignalDirection.SELL,
                    SignalDirection.EXIT,
                }:
                    side = (
                        OrderSide.BUY if signal.direction == SignalDirection.BUY else OrderSide.SELL
                    )
                    created = OrderEvent(
                        session_id=paper_session.id,
                        order_id=new_id(),
                        strategy_id=signal.strategy_id,
                        symbol=signal.symbol,
                        side=side,
                        quantity=signal.intended_quantity,
                        created_at=signal.timestamp,
                        status=OrderStatus.CREATED,
                    )
                    checked = risk.check(created, portfolio, market_event.open)
                    self._persist_order(checked)
                    sequence = self._record_event(
                        paper_session.id,
                        sequence,
                        EventType.ORDER,
                        checked.created_at,
                        _event_payload(checked),
                    )
                    if checked.status == OrderStatus.SUBMITTED:
                        fill = broker.submit_order(checked, market_event.open)
                        self._persist_fill(fill)
                        portfolio.apply_fill(fill)
                        filled_orders += 1
                        sequence = self._record_event(
                            paper_session.id,
                            sequence,
                            EventType.FILL,
                            fill.timestamp,
                            _event_payload(fill),
                        )
                    else:
                        rejected_orders += 1

                portfolio.mark_price(market_event.symbol, market_event.close)
                snapshot = portfolio.snapshot(paper_session.id, market_event.timestamp)
                sequence = self._record_event(
                    paper_session.id,
                    sequence,
                    EventType.PORTFOLIO,
                    snapshot.timestamp,
                    _event_payload(snapshot),
                )
                strategy.observe(market_event)

            final_snapshot = portfolio.snapshot(paper_session.id, bars[-1].timestamp)
            paper_session.status = "completed"
            paper_session.ended_at = _utcnow()
            paper_session.final_portfolio = _event_payload(final_snapshot)
            paper_session.metrics = {
                "market_events": market_events,
                "signals": signal_events,
                "orders": filled_orders + rejected_orders,
                "fills": filled_orders,
                "rejected_orders": rejected_orders,
                "ending_equity": final_snapshot.equity,
                "realized_pnl": final_snapshot.realized_pnl,
                "unrealized_pnl": final_snapshot.unrealized_pnl,
                "transaction_costs": final_snapshot.transaction_costs,
                "runtime_ms": round((time.perf_counter() - started) * 1000.0, 6),
            }
            self._record_event(
                paper_session.id,
                sequence,
                EventType.SESSION,
                paper_session.ended_at,
                {"status": "completed", "metrics": paper_session.metrics},
            )
        except Exception as exc:
            paper_session.status = "failed"
            paper_session.error_message = str(exc)
            paper_session.ended_at = _utcnow()
            self._record_event(
                paper_session.id,
                sequence,
                EventType.ERROR,
                paper_session.ended_at,
                {"error": str(exc)},
            )
            raise

        self.session.flush()
        self.session.refresh(paper_session)
        return paper_session

    def _persist_order(self, order: OrderEvent) -> None:
        self.session.add(
            PaperOrderRecord(
                id=order.order_id,
                session_id=order.session_id,
                strategy_id=order.strategy_id,
                symbol=order.symbol,
                side=order.side.value,
                quantity=Decimal(str(order.quantity)),
                status=order.status.value,
                created_at=order.created_at,
                rejection_reason=order.reason,
            )
        )

    def _persist_fill(self, fill: FillEvent) -> None:
        self.session.add(
            PaperFillRecord(
                id=fill.fill_id,
                session_id=fill.session_id,
                order_id=fill.order_id,
                strategy_id=fill.strategy_id,
                symbol=fill.symbol,
                side=fill.side.value,
                quantity=Decimal(str(fill.quantity)),
                price=Decimal(str(fill.price)),
                gross_notional=Decimal(str(fill.gross_notional)),
                fees=Decimal(str(fill.fees)),
                slippage_cost=Decimal(str(fill.slippage_cost)),
                timestamp=fill.timestamp,
            )
        )

    def _record_event(
        self,
        session_id: UUID,
        sequence: int,
        event_type: EventType,
        timestamp: datetime | None,
        payload: dict[str, Any],
    ) -> int:
        next_sequence = sequence + 1
        self.session.add(
            PaperTraceEventRecord(
                session_id=session_id,
                sequence=next_sequence,
                event_type=event_type.value,
                timestamp=timestamp,
                payload=payload,
            )
        )
        return next_sequence


def _event_payload(event: Any) -> dict[str, Any]:
    payload = asdict(event)
    payload.pop("session_id", None)
    for key, value in list(payload.items()):
        payload[key] = _json_safe_value(value)
    return payload


def _json_safe_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_safe_value(value) for key, value in payload.items()}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return _json_safe_dict(value)
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    return value


def _utcnow() -> datetime:
    return datetime.now(UTC)
