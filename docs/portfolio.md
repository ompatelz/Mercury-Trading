# Portfolio Construction and Dynamic Allocation

Mercury evaluates candidate strategies as a portfolio using aligned, timestamped validation return series. It never averages final strategy metrics: each portfolio return is computed from the strategy returns available at that point in time.

## Construction

Campaign finalization takes leading validation candidates and records a reproducible portfolio definition: candidate and experiment-version IDs, universe, validation period, allocation/dynamic method, rebalance schedule, constraints, and transaction-cost assumption. The portfolio ID is the persisted `portfolio_evaluations.id`.

Supported initial allocation methods are deliberately interpretable:

- `equal_weight`
- `inverse_volatility`
- `risk_parity` (iterative equal risk contribution)

Constraints are validated before simulation. Mercury reports explicit rejection reasons for minimum/maximum strategy weights, family exposure, asset exposure, portfolio leverage, and rebalance turnover.

## Compatibility and contribution

For every pair, Mercury stores aligned return correlation, signal-sign correlation, trade overlap, drawdown overlap, family similarity, and whether weak regimes are shared or complementary. It also stores the incremental Sharpe and drawdown change for each member, calculated by removing it from the portfolio—not by assuming every additional strategy helps.

## Dynamic allocation and safety

`static`, `volatility_scaling`, `risk_based`, and `performance_aware` rules are deterministic. Weekly/monthly rebalances record old/new weights, turnover, cost, and reason. At timestamp *t*, dynamic rules receive only `returns[:t]`; the current return and all future labels are unavailable. Portfolio search and ranking use validation/OOS streams; the campaign's final test split remains locked until candidate selection is complete.

## Evaluation and dashboard

Results include total/annualized return, volatility, Sharpe, Sortino, maximum drawdown, turnover, cost, diversification ratio, worst period, and per-strategy return/risk contribution. The campaign dashboard response exposes portfolio return series, compatibility, rebalances, incremental benefit, and ranking explanation. The API is research-only; it makes no real-money execution path available.

## Reading order

1. `app/portfolio/engine.py` — allocation, compatibility, simulation, and no-lookahead dynamic weighting.
2. `app/campaigns/portfolio.py` — maps persisted campaign candidates to the portfolio engine and records ranking evidence.
3. `app/experiments/service.py` — persists the return-series source artifact.
4. `app/campaigns/service.py` — finalizes candidate portfolios after validation.
5. `app/dashboard/service.py` — exposes stored portfolio research views.
