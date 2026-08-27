import threading
import time
from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.backtesting.registry import validate_strategy_spec
from app.core.config import get_settings
from app.market_data.live import LiveFeedState, LiveMarketBar, LiveMarketDataProvider
from app.market_data.repository import MarketDataRepository
from app.models.paper_trading import PaperFillRecord, PaperOrderRecord, PaperTradingSession
from app.paper_trading.broker import PaperBroker
from app.paper_trading.clock import MarketClock
from app.paper_trading.events import (
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderStatus,
    SignalDirection,
    new_id,
)
from app.paper_trading.execution import ExecutionConfig
from app.paper_trading.monitoring import (
    ComponentHealth,
    ComponentStatus,
    StrategyMonitoringState,
    live_update_hub,
)
from app.paper_trading.portfolio import Portfolio
from app.paper_trading.repository import PaperTradingRepository
from app.paper_trading.risk import RiskConfig, RiskEngine
from app.paper_trading.schemas import LivePaperTradingSessionCreateRequest
from app.paper_trading.service import _event_payload
from app.paper_trading.strategy import MovingAverageSignalStrategy


class LivePaperTradingService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        provider: LiveMarketDataProvider,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self._runners: dict[UUID, LiveSessionRunner] = {}

    def create_session(self, request: LivePaperTradingSessionCreateRequest) -> PaperTradingSession:
        if get_settings().execution_mode != "PAPER":
            raise ValueError("live execution is disabled unless EXECUTION_MODE=PAPER")
        with self.session_factory() as session:
            paper_session = _create_live_session_record(session, request)
            session.commit()
            session.refresh(paper_session)
            session_id = paper_session.id

        runner = LiveSessionRunner(
            session_factory=self.session_factory,
            provider=self.provider,
            request=request,
            session_id=session_id,
        )
        self._runners[session_id] = runner
        if request.max_events is None:
            runner.start()
        else:
            runner.run()
        with self.session_factory() as session:
            refreshed = PaperTradingRepository(session).get_session(session_id)
            if refreshed is None:
                raise ValueError("live session was not persisted")
            return refreshed

    def stop_session(self, session_id: UUID) -> PaperTradingSession:
        runner = self._runners.get(session_id)
        if runner is not None:
            runner.stop()
        with self.session_factory() as session:
            paper_session = PaperTradingRepository(session).get_session(session_id)
            if paper_session is None:
                raise ValueError("session not found")
            terminal_statuses = {LiveFeedState.STOPPED.value, LiveFeedState.FAILED.value}
            if paper_session.status not in terminal_statuses:
                paper_session.status = LiveFeedState.STOPPED.value
                paper_session.ended_at = datetime.now(UTC)
                session.commit()
                session.refresh(paper_session)
            return paper_session

    def health(self) -> list[ComponentHealth]:
        return [
            ComponentHealth(
                component="Market Data",
                status=ComponentStatus.HEALTHY,
                reason=f"provider={self.provider.source}",
            ),
            ComponentHealth(
                component="Strategy Runner",
                status=ComponentStatus.HEALTHY,
                reason=(
                    "active_sessions="
                    f"{sum(1 for runner in self._runners.values() if runner.is_alive())}"
                ),
            ),
            ComponentHealth(component="Paper Broker", status=ComponentStatus.HEALTHY),
            ComponentHealth(component="Workers", status=ComponentStatus.HEALTHY),
        ]


class LiveSessionRunner:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        provider: LiveMarketDataProvider,
        request: LivePaperTradingSessionCreateRequest,
        session_id: UUID,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.request = request
        self.session_id = session_id
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.monitoring = StrategyMonitoringState(session_id=session_id, status="created")

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self.run,
            name=f"live-paper-{self.session_id}",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=5.0)

    def is_alive(self) -> bool:
        return bool(self.thread is not None and self.thread.is_alive())

    def run(self) -> None:
        sequence = 0
        peak_equity = self.request.initial_cash
        market_events = 0
        signals = 0
        submitted_orders = 0
        fills = 0
        rejected_orders = 0
        feed_disconnects = 0
        strategy_errors = 0
        malformed_events = 0
        previous_market_timestamp: datetime | None = None
        portfolio = Portfolio(self.request.initial_cash)
        risk_config = RiskConfig(
            max_position_quantity=self.request.max_position_quantity,
            max_order_value=self.request.max_order_value,
            max_gross_exposure_pct=self.request.max_gross_exposure_pct,
            commission_bps=self.request.commission_bps,
            slippage_bps=self.request.slippage_bps,
        )
        risk = RiskEngine(risk_config)
        broker = PaperBroker(
            commission_bps=self.request.commission_bps,
            slippage_bps=self.request.slippage_bps,
            execution_config=ExecutionConfig(
                model=self.request.execution_model,
                spread_model=self.request.spread_model,
                fixed_spread_bps=self.request.fixed_spread_bps,
                slippage_bps=self.request.slippage_bps,
                max_participation_rate=self.request.max_participation_rate,
                impact_coefficient_bps=self.request.impact_coefficient_bps,
                latency_bars=self.request.latency_bars,
            ),
        )
        strategy = MovingAverageSignalStrategy(
            fast_window=self.request.strategy_parameters["fast_window"],
            slow_window=self.request.strategy_parameters["slow_window"],
            target_exposure_pct=self.request.target_exposure_pct,
        )
        clock = MarketClock()

        try:
            with self.session_factory() as session:
                sequence = self._record_event(
                    session,
                    sequence,
                    EventType.SESSION,
                    None,
                    {"status": LiveFeedState.CONNECTING.value, "source": self.provider.source},
                )
                self._set_status(session, LiveFeedState.CONNECTING)
                self._warm_up(session, strategy)
                sequence = self._record_event(
                    session,
                    sequence,
                    EventType.SESSION,
                    None,
                    {
                        "status": "warmup_complete",
                        "warmup_bars": strategy.history_size,
                    },
                )
                session.commit()

            attempts = 0
            while not self.stop_event.is_set():
                try:
                    with self.session_factory() as session:
                        self._set_status(session, LiveFeedState.CONNECTED)
                        session.commit()
                    for bar in self.provider.stream_bars(
                        symbol=self.request.symbol,
                        interval=self.request.interval,
                        stop_requested=self.stop_event,
                    ):
                        if self.stop_event.is_set():
                            break
                        attempts = 0
                        event_started = time.perf_counter()
                        market_event = _market_event_from_bar(
                            bar,
                            session_id=self.session_id,
                            sequence=market_events + 1,
                        )
                        if (
                            previous_market_timestamp is not None
                            and market_event.timestamp <= previous_market_timestamp
                        ):
                            malformed_events += 1
                            with self.session_factory() as session:
                                sequence = self._record_event(
                                    session,
                                    sequence,
                                    EventType.ERROR,
                                    market_event.timestamp,
                                    {
                                        "error": "live market events must be chronological",
                                        "stage": "market_data",
                                    },
                                )
                                self._update_session_metrics(
                                    session,
                                    {
                                        "market_events_received": market_events,
                                        "signals_generated": signals,
                                        "orders_submitted": submitted_orders,
                                        "orders_rejected": rejected_orders,
                                        "fills": fills,
                                        "strategy_errors": strategy_errors,
                                        "feed_disconnects": feed_disconnects,
                                        "malformed_events": malformed_events,
                                        "monitoring": self.monitoring.as_dict(),
                                    },
                                    {},
                                )
                                session.commit()
                            continue
                        previous_market_timestamp = market_event.timestamp
                        market_events += 1
                        with self.session_factory() as session:
                            self._set_status(session, LiveFeedState.STREAMING)
                            sequence = self._record_event(
                                session,
                                sequence,
                                EventType.MARKET,
                                market_event.timestamp,
                                _event_payload(market_event) | {"source": bar.source},
                            )
                            portfolio.mark_price(market_event.symbol, market_event.open)
                            market_state = clock.state_at(market_event.timestamp)
                            signal_started = time.perf_counter()
                            try:
                                signal = strategy.on_market(market_event, portfolio)
                            except Exception as exc:
                                strategy_errors += 1
                                self.monitoring.record_error(str(exc))
                                sequence = self._record_event(
                                    session,
                                    sequence,
                                    EventType.ERROR,
                                    market_event.timestamp,
                                    {"error": str(exc), "stage": "strategy"},
                                )
                                strategy.observe(market_event)
                                session.commit()
                                continue
                            event_to_signal_ms = _elapsed_ms(signal_started, event_started)
                            signals += 1
                            sequence = self._record_event(
                                session,
                                sequence,
                                EventType.SIGNAL,
                                signal.timestamp,
                                _event_payload(signal) | {"market_session": market_state.value},
                            )
                            self.monitoring.last_market_event = _event_payload(market_event) | {
                                "source": bar.source,
                                "market_session": market_state.value,
                            }
                            self.monitoring.last_signal = _event_payload(signal)

                            order_started = time.perf_counter()
                            if signal.direction in {
                                SignalDirection.BUY,
                                SignalDirection.SELL,
                                SignalDirection.EXIT,
                            }:
                                outside_market_hours = (
                                    self.request.respect_market_hours
                                    and not clock.can_submit_orders(market_event.timestamp)
                                )
                                if outside_market_hours:
                                    rejected_orders += 1
                                    sequence = self._record_event(
                                        session,
                                        sequence,
                                        EventType.ERROR,
                                        market_event.timestamp,
                                        {
                                            "error": "order blocked outside open market session",
                                            "market_session": market_state.value,
                                        },
                                    )
                                else:
                                    order = _order_from_signal(signal)
                                    checked = risk.check(order, portfolio, market_event.open)
                                    self._persist_order(session, checked)
                                    self.monitoring.last_order = _event_payload(checked)
                                    sequence = self._record_event(
                                        session,
                                        sequence,
                                        EventType.ORDER,
                                        checked.created_at,
                                        _event_payload(checked),
                                    )
                                    if checked.status == OrderStatus.SUBMITTED:
                                        fill_started = time.perf_counter()
                                        fill = broker.submit_order(checked, market_event.open)
                                        self._persist_fill(session, fill)
                                        portfolio.apply_fill(fill)
                                        fills += 1
                                        submitted_orders += 1
                                        sequence = self._record_event(
                                            session,
                                            sequence,
                                            EventType.FILL,
                                            fill.timestamp,
                                            _event_payload(fill),
                                        )
                                        order_to_fill_ms = _elapsed_ms(
                                            time.perf_counter(),
                                            fill_started,
                                        )
                                    else:
                                        rejected_orders += 1
                                        order_to_fill_ms = 0.0
                            else:
                                order_to_fill_ms = 0.0

                            portfolio.mark_price(market_event.symbol, market_event.close)
                            snapshot = portfolio.snapshot(self.session_id, market_event.timestamp)
                            peak_equity = max(peak_equity, snapshot.equity)
                            drawdown = (
                                (peak_equity - snapshot.equity) / peak_equity
                                if peak_equity
                                else 0.0
                            )
                            latency = {
                                "event_to_signal_ms": event_to_signal_ms,
                                "signal_to_order_ms": _elapsed_ms(
                                    time.perf_counter(),
                                    order_started,
                                ),
                                "order_to_fill_ms": order_to_fill_ms,
                                "total_pipeline_ms": _elapsed_ms(
                                    time.perf_counter(),
                                    event_started,
                                ),
                            }
                            self.monitoring.current_position = snapshot.positions
                            self.monitoring.pnl = {
                                "realized": snapshot.realized_pnl,
                                "unrealized": snapshot.unrealized_pnl,
                            }
                            self.monitoring.equity = snapshot.equity
                            self.monitoring.drawdown = round(drawdown, 8)
                            self.monitoring.number_of_trades = fills
                            self.monitoring.rejected_orders = rejected_orders
                            self.monitoring.processing_latency_ms = latency
                            self.monitoring.status = LiveFeedState.STREAMING.value
                            sequence = self._record_event(
                                session,
                                sequence,
                                EventType.PORTFOLIO,
                                snapshot.timestamp,
                                _event_payload(snapshot) | {"drawdown": round(drawdown, 8)},
                            )
                            strategy.observe(market_event)
                            self._update_session_metrics(
                                session,
                                {
                                    "market_events_received": market_events,
                                    "signals_generated": signals,
                                    "orders_submitted": submitted_orders,
                                    "orders_rejected": rejected_orders,
                                    "fills": fills,
                                    "strategy_errors": strategy_errors,
                                    "feed_disconnects": feed_disconnects,
                                    "malformed_events": malformed_events,
                                    "processing_latency": latency,
                                    "monitoring": self.monitoring.as_dict(),
                                },
                                _event_payload(snapshot),
                            )
                            session.commit()
                            live_update_hub.publish(
                                self.session_id,
                                "portfolio_update",
                                _event_payload(snapshot),
                            )
                            reached_event_limit = (
                                self.request.max_events is not None
                                and market_events >= self.request.max_events
                            )
                            if reached_event_limit:
                                self.stop_event.set()
                                break
                    if self.request.max_events is not None or self.stop_event.is_set():
                        break
                    break
                except Exception as exc:
                    feed_disconnects += 1
                    attempts += 1
                    with self.session_factory() as session:
                        self._set_status(session, LiveFeedState.RECONNECTING)
                        sequence = self._record_event(
                            session,
                            sequence,
                            EventType.ERROR,
                            datetime.now(UTC),
                            {"error": str(exc), "stage": "market_data", "attempt": attempts},
                        )
                        session.commit()
                    if attempts > self.request.max_reconnect_attempts:
                        raise
                    time.sleep(self.request.reconnect_backoff_seconds)
            with self.session_factory() as session:
                self._set_status(session, LiveFeedState.STOPPED)
                paper_session = PaperTradingRepository(session).get_session(self.session_id)
                if paper_session is not None:
                    paper_session.ended_at = datetime.now(UTC)
                sequence = self._record_event(
                    session,
                    sequence,
                    EventType.SESSION,
                    datetime.now(UTC),
                    {"status": LiveFeedState.STOPPED.value},
                )
                session.commit()
        except Exception as exc:
            with self.session_factory() as session:
                self._set_status(session, LiveFeedState.FAILED, str(exc))
                self._record_event(
                    session,
                    sequence,
                    EventType.ERROR,
                    datetime.now(UTC),
                    {"error": str(exc), "stage": "live_runner"},
                )
                session.commit()

    def _warm_up(self, session: Session, strategy: MovingAverageSignalStrategy) -> None:
        if self.request.warmup_start is None or self.request.warmup_end is None:
            return
        bars = MarketDataRepository(session).list_bars(
            symbol=self.request.symbol,
            interval=self.request.interval,
            start=self.request.warmup_start,
            end=self.request.warmup_end,
        )
        if len(bars) < self.request.strategy_parameters["slow_window"]:
            raise ValueError("not enough warm-up bars for strategy slow_window")
        for sequence, bar in enumerate(bars, start=1):
            strategy.observe(
                MarketEvent(
                    session_id=self.session_id,
                    timestamp=bar.timestamp,
                    symbol=bar.symbol,
                    interval=bar.interval,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=bar.volume,
                    sequence=sequence,
                )
            )

    def _set_status(
        self,
        session: Session,
        status: LiveFeedState,
        error_message: str | None = None,
    ) -> None:
        paper_session = PaperTradingRepository(session).get_session(self.session_id)
        if paper_session is not None:
            paper_session.status = status.value
            paper_session.error_message = error_message
        self.monitoring.status = status.value

    def _record_event(
        self,
        session: Session,
        sequence: int,
        event_type: EventType,
        timestamp: datetime | None,
        payload: dict[str, Any],
    ) -> int:
        from app.models.paper_trading import PaperTraceEventRecord

        next_sequence = sequence + 1
        session.add(
            PaperTraceEventRecord(
                session_id=self.session_id,
                sequence=next_sequence,
                event_type=event_type.value,
                timestamp=timestamp,
                payload=payload,
            )
        )
        live_update_hub.publish(self.session_id, event_type.value.lower(), payload)
        return next_sequence

    def _persist_order(self, session: Session, order: OrderEvent) -> None:
        session.add(
            PaperOrderRecord(
                id=order.order_id,
                session_id=order.session_id,
                strategy_id=order.strategy_id,
                symbol=order.symbol,
                side=order.side.value,
                quantity=order.quantity,
                status=order.status.value,
                created_at=order.created_at,
                rejection_reason=order.reason,
            )
        )

    def _persist_fill(self, session: Session, fill: FillEvent) -> None:
        session.add(
            PaperFillRecord(
                id=fill.fill_id,
                session_id=fill.session_id,
                order_id=fill.order_id,
                strategy_id=fill.strategy_id,
                symbol=fill.symbol,
                side=fill.side.value,
                quantity=fill.quantity,
                price=fill.price,
                gross_notional=fill.gross_notional,
                fees=fill.fees,
                slippage_cost=fill.slippage_cost,
                timestamp=fill.timestamp,
            )
        )

    def _update_session_metrics(
        self,
        session: Session,
        metrics: dict[str, Any],
        portfolio: dict[str, Any],
    ) -> None:
        paper_session = PaperTradingRepository(session).get_session(self.session_id)
        if paper_session is not None:
            paper_session.metrics = metrics
            if portfolio:
                paper_session.final_portfolio = portfolio


def _create_live_session_record(
    session: Session,
    request: LivePaperTradingSessionCreateRequest,
) -> PaperTradingSession:
    validated = validate_strategy_spec(request.strategy_name, request.strategy_parameters)
    if request.execution_mode.value != "PAPER":
        raise ValueError("only PAPER execution mode is supported")
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
        start_date=request.warmup_start or date.today(),
        end_date=request.warmup_end or date.today(),
        execution_mode=request.execution_mode.value,
        status=LiveFeedState.DISCONNECTED.value,
        initial_cash=request.initial_cash,
        commission_bps=request.commission_bps,
        slippage_bps=request.slippage_bps,
        risk_config=asdict(risk_config),
        metrics={},
        final_portfolio={},
        error_message=None,
    )
    session.add(paper_session)
    session.flush()
    request.strategy_parameters = validated
    return paper_session


def _market_event_from_bar(bar: LiveMarketBar, *, session_id: UUID, sequence: int) -> MarketEvent:
    return MarketEvent(
        session_id=session_id,
        timestamp=bar.timestamp,
        symbol=bar.symbol,
        interval=bar.interval,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        sequence=sequence,
    )


def _order_from_signal(signal: Any) -> OrderEvent:
    side = OrderSide.BUY if signal.direction == SignalDirection.BUY else OrderSide.SELL
    return OrderEvent(
        session_id=signal.session_id,
        order_id=new_id(),
        strategy_id=signal.strategy_id,
        symbol=signal.symbol,
        side=side,
        quantity=signal.intended_quantity,
        created_at=signal.timestamp,
        status=OrderStatus.CREATED,
    )


def _elapsed_ms(end: float, start: float) -> float:
    return round((end - start) * 1000.0, 6)
