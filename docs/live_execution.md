# Live Execution

Mercury live execution is live paper trading only. Market data can come from a
real feed, but orders are routed exclusively through the `PaperBroker`.

## Flow

```text
Live Market Feed
  -> LiveMarketDataProvider
  -> LiveMarketBar
  -> MarketEvent
  -> MovingAverageSignalStrategy
  -> SignalEvent
  -> RiskEngine
  -> OrderEvent
  -> PaperBroker
  -> FillEvent
  -> PortfolioEvent
  -> Monitoring / Trace Events / WebSocket Updates
```

Historical replay and live execution share the same strategy, risk, paper
broker, and portfolio contracts. The provider boundary is the source-specific
part of the system.

## Providers

- `StaticLiveMarketDataProvider` is deterministic and used in tests.
- `YahooFinanceLiveMarketDataProvider` polls recent Yahoo Finance intraday bars,
  normalizes them, and emits unseen bars.

Configuration:

```text
EXECUTION_MODE=PAPER
LIVE_MARKET_DATA_PROVIDER=yahoo
LIVE_MARKET_DATA_POLL_SECONDS=30
YAHOO_AUTO_ADJUST=false
```

Yahoo Finance does not require credentials. Future providers that require
credentials must read them from environment variables and keep vendor-specific
payloads inside the provider module.

## Lifecycle

Live sessions move through explicit feed states:

```text
DISCONNECTED
  -> CONNECTING
  -> CONNECTED
  -> STREAMING
  -> RECONNECTING
  -> STOPPED
```

`FAILED` is recorded when reconnect attempts are exhausted or another unrecovered
runner error occurs. Bad market events and strategy exceptions are recorded as
trace errors instead of silently disappearing.

## Warm-Up

Strategies can be warmed from stored historical bars before live streaming:

```text
Historical Warm-Up
  -> Strategy State Ready
  -> Live Stream Starts
```

For moving-average crossover, warm-up must include at least `slow_window` bars.
Signals are not generated for warm-up bars; they only seed strategy history.

## Market Clock

`MarketClock` classifies timestamps as:

```text
PRE_MARKET
OPEN
CLOSED
```

Live session requests can set `respect_market_hours=true` to block order
submission outside the simple open session. The default is false so deterministic
tests and non-US development feeds can run without exchange-calendar
dependencies.

## Monitoring

Each live session stores monitoring data in the session metrics:

- latest market event
- latest signal
- latest order
- current position
- realized and unrealized PnL
- equity and drawdown
- trades and rejected orders
- processing latency
- errors
- feed disconnects

Latency fields:

```text
event_to_signal_ms
signal_to_order_ms
order_to_fill_ms
total_pipeline_ms
```

## API

Start a live paper session:

```bash
curl -X POST http://localhost:8000/live/sessions \
  -H "Content-Type: application/json" \
  -d '{"symbol":"MSFT","interval":"1m","strategy_parameters":{"fast_window":5,"slow_window":20},"execution_mode":"PAPER","warmup_start":"2024-01-01","warmup_end":"2024-02-01","initial_cash":10000}'
```

Inspect and stop:

```bash
curl http://localhost:8000/live/sessions/{session_id}
curl http://localhost:8000/live/sessions/{session_id}/metrics
curl http://localhost:8000/live/sessions/{session_id}/portfolio
curl http://localhost:8000/live/sessions/{session_id}/orders
curl http://localhost:8000/live/health
curl -X POST http://localhost:8000/live/sessions/{session_id}/stop
```

WebSocket updates are available at:

```text
ws://localhost:8000/live/sessions/{session_id}/ws
```

## CI Boundary

CI uses fake live feeds. It must not depend on real market-data availability,
internet access, market hours, or vendor credentials.
