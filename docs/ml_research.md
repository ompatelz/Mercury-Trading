# ML research

Mercury tests whether a simple, reproducible model adds tradable out-of-sample value; it does not predict prices or permit a model to alter portfolio state. The flow is point-in-time observations -> versioned features and target -> chronological train/validation/test -> scores -> the existing factor ranking and portfolio engine -> cost-aware backtest.

`MLExperimentDefinition` is the immutable recipe: algorithm, task/target, universe, feature versions, data fingerprint, temporal periods, preprocessing, hyperparameters, seed, and model version. The initial deterministic baselines are historical mean, ridge-style linear regression, and logistic regression. Tree models remain future candidates until they can be evaluated on the same locked fixtures.

Each observation carries `available_at` and a strictly future `target_timestamp`; invalid rows are rejected. The preprocessor is fitted exclusively on the train split, then applied unchanged to validation and test. Splits are chronological and non-overlapping. The cross-sectional task is evaluated with IC/rank IC; time-series and classification use the same temporal boundary but can use their relevant prediction metrics.

The registry persists model/data/feature lineage, test metrics, a checksum-addressed JSON artifact, and every OOS prediction with its input fingerprint. A decision record documents validation. `TRAIN_VALIDATION_GAP_HIGH`, `LOW_OOS_IC`, and `FEATURE_INSTABILITY` keep a candidate from automatic promotion. A later champion gate must compare factor baseline, Sharpe, drawdown, turnover, and execution costs using the existing portfolio/backtest services.

The `/ml-research/evaluate` endpoint accepts only structured observations and produces/persists a research candidate. It is intentionally research-only and has no live-order path.
