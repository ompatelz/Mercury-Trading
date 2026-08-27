# Research data

Mercury separates mutable provider ingestion from immutable research inputs. A backtest first pins a `DatasetVersion`: a validated, checksummed Parquet snapshot with its provider, universe, interval, coverage, schema version, adjustment policy, and structured quality report. PostgreSQL stores the version metadata, parent-to-child transformations, snapshots, feature definitions, and cache metadata; Parquet stores the time-series payload.

`DatasetLineage` records every ingest or declared transformation with its parent version, implementation version, parameters, and timestamp. A changed payload creates the next version; an unchanged payload reuses the existing immutable version. This makes `dataset_id + version_id` the durable experiment input, never a moving symbol label.

The quality gate rejects duplicate symbol/timestamp pairs, nulls, invalid OHLC relationships, negative volume, mixed/non-UTC timestamps, out-of-order rows, and unexpected intraday gaps. It reports rather than repairs; any cleaning or adjustment must be written as a new child version and lineage edge. Adjustment policy is explicit and defaults to `unadjusted`.

The small internal feature store versions feature definitions separately from their materializations. It supports deterministic Polars rolling means and returns today, caches results as Parquet by `(dataset version, feature version, parameter hash)`, and never crosses dataset versions. Rolling expressions are trailing-window Polars expressions, so a value at time `t` has no future rows available to it. Full-dataset normalization is deliberately not part of the feature API.

Each new backtest stores its dataset-version reference, feature-version inputs, and immutable fingerprint in both columns and reproducibility metadata. Existing row-level market data is snapshotted once on first use, preserving compatibility while ensuring completed experiments no longer follow later downloads. Campaigns may supply a `dataset_snapshot_id` and an explicit feature set; campaign train, validation, walk-forward, and locked-test backtests resolve their symbol-specific dataset versions from that snapshot.

Reproduction defaults to the experiment's recorded dataset version. Later edits to mutable provider rows do not affect a completed experiment. `POST /experiments/{id}/reproduce?dataset_version_id={other_version}` intentionally replays against a different immutable version and reports `data_mismatch` plus `dataset_version_override` when the data identity changes.

Metadata APIs are `GET /datasets`, `GET /datasets/{id}/versions`, `GET /datasets/{id}/lineage`, `GET /datasets/snapshots`, `POST /datasets/snapshots`, `GET /features`, and `GET /features/{id}/versions`; `POST /features` registers a versioned feature definition and `POST /features/{version_id}/materialize` builds or reuses a cached feature payload. Bulk bars remain under `/market-data`. The dashboard's Research Data section reads the catalog and shows dataset versions, row counts, quality status, adjustment policy, and checksums.

Read map:

1. `app/models/data.py` for metadata tables and relationships.
2. `app/data/service.py` for quality rules, immutable Parquet storage, lineage, snapshots, and feature cache behavior.
3. `app/experiments/service.py` for dataset/feature pinning in backtests.
4. `app/campaigns/service.py` for snapshot inheritance across campaign backtests.
5. `app/research_artifacts/service.py` for immutable reproduction and mismatch reporting.
6. `frontend/src/App.tsx` for the dashboard catalog surface.

Polars is used for the new analytical storage and trailing calculations because it is already a Mercury dependency. No pandas path was replaced: a benchmark-driven comparison is required before migrating any established execution path.
