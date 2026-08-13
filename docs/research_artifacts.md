# Research Artifacts

Mercury research reports are generated from structured database artifacts, not
free-form model output. The source of truth is the `research_artifacts` table.
Markdown is an export of that structured record.

## Reproducible Experiments

New completed backtests store a reproducibility snapshot in
`Experiment.run_metadata["reproducibility"]`:

- experiment id
- strategy name and parameters
- symbol, interval, and exact date range
- transaction-cost and slippage assumptions
- random seed field, currently `null` for deterministic moving-average runs
- backtester and strategy versions
- current Git commit when available
- environment fingerprint
- configuration fingerprint
- market-data fingerprint

The intended chain is:

```text
Experiment ID
  -> stored configuration
  -> same market-data fingerprint
  -> same strategy implementation
  -> same metric outputs within explicit tolerances
```

Older experiments can still produce reports, but fields that were not captured
at run time are marked as unavailable instead of being inferred.

## Artifact Generation

`ResearchArtifactService` builds experiment and campaign artifacts from persisted
Mercury data:

```text
Experiment
  -> Backtest metrics
  -> Trades
  -> Regime metrics
  -> Campaign evaluation when linked
  -> Research experiment critique when linked
  -> Memory lessons and trace events when linked
  -> ResearchArtifact
```

Experiment artifacts include:

- hypothesis
- methodology
- strategy definition
- dataset and validation method
- measured performance metrics
- risk metrics and flags
- regime metrics
- critic and memory summaries
- measured result and separate interpretation
- provenance references
- reproducibility metadata
- chart data for equity, drawdown, and returns distribution

Campaign artifacts aggregate:

- objective, constraints, and budget
- hypotheses tested
- completed experiment ids
- rejected approaches
- top ranked candidates
- locked test results
- walk-forward summaries
- campaign-level risk flags
- final conclusions

## Reports

The Markdown report is generated from the artifact fields. It contains sections
for experiment summary, hypothesis, strategy, dataset and validation,
performance, risk analysis, regime performance, overfitting checks, trades and
costs, conclusion, and reproducibility.

Report text is deliberately conservative. It can explain measured values, but it
does not invent unavailable metrics or change stored measurements.

## Reproduction

Use:

```bash
curl -X POST http://localhost:8000/experiments/{experiment_id}/reproduce
```

or:

```bash
python scripts/reproduce_experiment.py {experiment_id}
```

The reproduction check:

1. Loads the stored experiment configuration.
2. Loads current market data for the same symbol, interval, and date range.
3. Rebuilds the moving-average strategy from stored parameters.
4. Runs the deterministic backtest without creating a new experiment row.
5. Compares reproduced metrics to original metrics using explicit tolerances.
6. Reports changed inputs such as market data, configuration, commit, or
   environment fingerprint.

A successful result has `match: true` and no blocking differences. Mercury does
not claim reproduction success when fingerprints or metrics differ.

## API

```text
GET  /experiments/{experiment_id}/report
GET  /experiments/{experiment_id}/report?format=markdown
POST /experiments/{experiment_id}/reproduce
GET  /campaigns/{campaign_id}/report
GET  /research-artifacts/{artifact_id}
GET  /research-artifacts/{artifact_id}?format=markdown
```

`GET /campaigns/{campaign_id}/report` preserves the existing campaign report
fields and includes the structured artifact under `artifact`.

## Dashboard

The dashboard opens the selected experiment report through the backend report
endpoint. It displays measured results, interpretation, reproducibility
metadata, chart data, export links, and an explicit reproduction action. Heavy
report generation remains in the backend.

## Storage

Artifacts are currently stored in the database with JSON fields and a Markdown
export field. `export_metadata.storage` records this as `database`. The service
boundary keeps file or object-storage exports separate from report construction
so future local filesystem or S3 storage can be added without changing the
artifact schema.
