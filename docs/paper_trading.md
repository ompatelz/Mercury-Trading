# Paper Trading

Mercury's paper-trading layer simulates live-style execution over stored
historical bars. It is deterministic, synchronous, and paper-only.

## Event Flow

```text
MarketBar rows
  -> HistoricalReplayStream
  -> MarketEvent
  -> MovingAverageSignalStrategy
  -> SignalEvent
  -> RiskEngine
  -> OrderEvent
  -> PaperBroker
  -> FillEvent
  -> Portfolio
  -> PortfolioEvent
```

The replay stream preserves source timestamps and processes bars in ascending
timestamp order. The strategy receives the current market event, but its signal
calculation uses only bars observed before that event. After risk, broker, and
portfolio updates complete, the current event is appended to strategy history.

## Safety

Only `execution_mode = PAPER` is accepted. Mercury does not include live broker
credentials, live order submission, or a real-money execution adapter.

## Components

- `app/paper_trading/events.py`: typed market, signal, order, fill, portfolio,
  and session event structures.
- `app/paper_trading/stream.py`: `MarketDataStream` interface and
  `HistoricalReplayStream` implementation.
- `app/paper_trading/strategy.py`: adapter from the registered moving-average
  strategy parameters to live-style signal events.
- `app/paper_trading/risk.py`: deterministic checks for invalid quantity,
  duplicate orders, cash, max position, max order value, and gross exposure.
- `app/paper_trading/broker.py`: `PaperBroker` market-order fills with explicit
  commission and slippage assumptions.
- `app/paper_trading/portfolio.py`: cash, position, PnL, equity, exposure, and
  transaction-cost accounting updated from fills.
- `app/paper_trading/service.py`: synchronous session runner and persistence.
- `app/api/routes/paper_trading.py`: resource endpoints for sessions, orders,
  trades, and portfolio snapshots.

## API

```bash
curl -X POST http://localhost:8000/paper-trading/sessions \
  -H "Content-Type: application/json" \
  -d '{"symbol":"MSFT","start":"2024-01-01","end":"2024-06-01","interval":"1d","strategy_parameters":{"fast_window":5,"slow_window":20},"execution_mode":"PAPER","initial_cash":10000,"commission_bps":1,"slippage_bps":2}'

curl http://localhost:8000/paper-trading/sessions/{session_id}
curl http://localhost:8000/paper-trading/sessions/{session_id}/orders
curl http://localhost:8000/paper-trading/sessions/{session_id}/trades
curl http://localhost:8000/paper-trading/sessions/{session_id}/portfolio
```

Market data must be ingested before creating a paper-trading session.

## Persistence

`paper_trading_sessions` stores session inputs, risk configuration, metrics, and
the final portfolio. `paper_orders`, `paper_fills`, and `paper_trace_events`
store the reconstructable execution record.
