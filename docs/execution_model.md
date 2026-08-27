# Execution model

Mercury remains strictly PAPER-only. The execution model is a deterministic
simulation designed to reveal fragile strategies, not to reproduce an exchange.

## Flow

`Market event -> strategy -> risk -> order -> latency queue -> execution model -> fill -> portfolio`

`IdealExecution` fills the full order at the bar mid. `BasicSlippageExecution`
uses the executable quote side and a configured bps slippage cost.
`MicrostructureExecution` additionally limits a bar's aggregate fill quantity to
`volume * max_participation_rate` and applies a square-root participation impact.
The Python implementation is the correctness reference; this path is not a C++
optimization target until profiling demonstrates a bottleneck.

## Market state and quotes

`MarketState` contains timestamp, symbol, bid, ask, mid, last price, volume, and
quote source. When bid and ask are supplied by a market event they are used.
OHLCV bars do not contain a book, so Mercury derives a symmetric quote from
`fixed_spread_bps` and records `quote_source=synthetic_fixed_bps`. It never
pretends that synthetic quotes represent Level 2 depth.

Buys execute at the ask and sells at the bid for quote-based models. Slippage is
an explicit bps adjustment. Impact is `mid * impact_coefficient_bps / 10,000 *
sqrt(fill_quantity / volume)`. These are transparent stress assumptions, not
institutional-realism claims.

## Liquidity, fills, and latency

Microstructure liquidity is shared by the order queue for a symbol and bar. An
order beyond the participation cap becomes `PARTIALLY_FILLED`; individual fills,
filled quantity, remaining quantity, and average fill price are persisted.
Portfolio cash and positions move only when a fill is applied.

Historical latency is an integer number of chronological replay events. A signal
with `latency_bars=1` reaches the next event, so it uses that future event's
market state rather than the signal bar. This is deterministic and prevents the
execution model from using later prices at signal time. Live paper sessions use
the same cost-model configuration, but do not yet defer live orders by event
count.

## Configuration and evidence

Requests accept `execution_model`, `spread_model`, `fixed_spread_bps`,
`slippage_bps`, `max_participation_rate`, `impact_coefficient_bps`, and
`latency_bars`. The complete versioned configuration is stored in the session
risk configuration and final metrics. Metrics include fill rate, partial fills,
average spread paid, estimated impact, unfilled quantity, and deterministic
liquidity/spread/impact flags.

There is intentionally no fabricated order book, stochastic fill process, hidden
calibration, real broker connection, or claim that these values forecast real
market execution. Strategy-ranking sensitivity runs and cross-strategy liquidity
netting remain a future orchestration concern; this model provides the stable
execution contract and evidence needed for those comparisons.
