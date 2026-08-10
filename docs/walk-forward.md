# Temporal Splits and Walk-Forward Analysis

Campaigns store a train/validation/test split:

```text
Training -> used for fitting or initial parameter checks
Validation -> used for ranking candidates
Test -> locked during exploration
```

The split validator rejects overlapping periods and periods outside the campaign
date range. This prevents accidental leakage from tuning directly against the
final test period.

Walk-forward analysis evaluates robustness across rolling windows:

```text
Train A -> Test A
Train B -> Test B
Train C -> Test C
```

Campaign jobs run deterministic walk-forward train/test backtests before the
locked final test split. Each completed campaign experiment stores the rolling
window definitions, train/test experiment IDs, window metrics, average
out-of-sample Sharpe, worst drawdown, return consistency, train/test
degradation, and parameter stability. The window builder and aggregation logic
are in `app/campaigns/walk_forward.py`.

Overfitting flags are generated in `app/campaigns/overfitting.py`. Current flags
include validation degradation, drawdown breach, excessive turnover, low trade
count, and weak validation performance.
