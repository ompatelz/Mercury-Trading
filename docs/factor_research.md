# Factor Research and Cross-Sectional Strategies

Mercury's factor engine is a small, deterministic research layer: a versioned universe and point-in-time inputs become factor scores, cross-sectional ranks, constrained weights, and forward-looking evidence. It is not a large factor zoo and it never executes generated Python.

## Definitions and data safety

`FactorDefinition` records a factor ID, name, version, input features, lookback, transformation, ranking method, direction, universe requirements, and preprocessing version. The initial price-only transformations are trailing return (momentum) and inverse trailing volatility (low-volatility). Value, quality, and size definitions may be stored, but must not be evaluated until their point-in-time fundamental inputs are available.

Every score has a timestamp and asset identity. Ranking and winsorized/z-score/rank normalization operate only within that timestamp's eligible universe. Missing scores are excluded; ties break by stable asset ID. Historical universe versions come from `alternative_data`; a universe labelled with `SURVIVORSHIP_BIAS_RISK` remains visibly limited.

## Strategy DSL and construction

`FactorStrategySpec` is a bounded data DSL: `UNIVERSE -> FACTOR -> RANK -> SELECT -> WEIGHT -> REBALANCE`. It supports a transparent equal- or weighted-score composite, top-N long-only or symmetric top/bottom quantile selection, equal/score/inverse-volatility weights, explicit cost assumptions, and sector or size neutralization. It compiles to a canonical, SHA-256-addressed plan. The reusable campaign portfolio engine remains the path for combining a factor strategy with time-series and other strategy return series.

## Evidence

The evaluator aligns factor scores to supplied future returns by timestamp, asset ID, and horizon. It reports Pearson IC, rank IC, IC series, Q1..Q5 (or requested quantiles), top-minus-bottom spread, decay across horizons, and rank turnover. It also reports factor exposures, sector-concentration and breadth warnings. A factor result is research evidence, not a promotion decision: campaign optimization must keep train/validation/walk-forward selection separate from the locked final test split.

## Interfaces and limitations

`POST /factor-research/validate` compiles a structured plan. `POST /factor-research/evaluate` returns the ranking, weights, exposures, flags, and evidence for supplied immutable, point-in-time scores/labels. Corporate actions, delistings, ticker changes, and historical membership must be addressed upstream by the existing data-lineage and asset-identity layers; missing coverage must be flagged rather than imputed silently.
