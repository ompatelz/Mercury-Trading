# Portfolio Evaluation

Phase 5 starts portfolio-level research without building a full institutional
optimizer. The campaign report ranks individual candidates first, then evaluates
the top strategies together.

Supported weighting methods:

- `equal_weight`
- `volatility_adjusted`
- `risk_parity`

The portfolio evaluator calculates combined return, volatility, portfolio
Sharpe, diversification benefit, and a simple strategy correlation matrix. The
correlation estimate uses strategy family and symbol similarity as a deterministic
starting point until full return-series persistence is added.

The implementation lives in `app/campaigns/portfolio.py`.
