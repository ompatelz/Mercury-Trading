# Alternative and Cross-Asset Research

Mercury accepts a limited set of cross-asset and alternative-data primitives. It does not fetch arbitrary web data during research or CI, and it remains strictly PAPER-only.

## Data types and provenance

Providers implement a small typed interface for market prices, macro, fundamental, or alternative observations. They standardize provider/version metadata, coverage, frequency, identity, and availability time; their value schemas remain independent. The persisted `/data-catalog` endpoint is the source of truth for agent and campaign input availability.

Each observation records `observation_at` and `available_at`. The latter controls point-in-time eligibility. A CPI value for January that was released in February cannot appear in a January feature. Fundamentals follow the same rule: report period is descriptive, while reported/available time controls use.

## Alignment

`align_asof` is an explicit as-of join. At a target time it chooses only the most recent release where `available_at <= target`. Forward fill, maximum staleness, and observation-date eligibility are policy inputs; unavailable, missing, and stale values are returned as visible statuses. Alignment policy must be carried in a feature's parameters, which are included in the existing deterministic feature-materialization cache hash.

## Assets, universes, and survivorship

`ResearchAsset` uses a stable internal identifier with symbol, asset class, venue, currency, timezone, and provider IDs. A versioned universe has effective dates, filters, memberships, and limitations. If historical membership cannot be reconstructed, it is explicitly labelled `SURVIVORSHIP_BIAS_RISK`; Mercury does not infer historic membership from a present-day universe.

## Cross-asset features

The initial transparent library contains relative strength, deterministic cross-sectional ranking, correlation, and yield-curve slope. It calculates values only; strategy narrative and portfolio allocation remain separate deterministic systems. Ranking ties break by stable asset identifier.

## Campaign and reproducibility rules

Campaigns can include `datasets.data_requirements` containing persisted provider names. Unknown requirements are rejected before hypotheses are planned. Dataset snapshots, feature versions, feature parameters (including alignment policy), and universe versions should be recorded by the calling campaign configuration. No external data calls are made in normal CI.
