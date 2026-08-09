# Research Memory

Mercury memory stores structured lessons from completed research experiments. It
does not store every model response.

Each lesson records:

- source research experiment ID
- backtest experiment ID
- hypothesis
- strategy family
- symbol and asset class
- deterministic market regime
- metrics
- risk flags and failure reasons
- critic summary and observations
- confidence, tags, embedding, and version metadata

Market regime is derived from stored price bars using deterministic rules for
direction, volatility, and trend consistency. The current embedding is a
deterministic hashed vector so CI does not depend on external model calls.

Retrieval combines filters such as symbol, strategy family, regime, and failure
type with cosine similarity. Results include source experiment IDs so memory use
is traceable.

Future pgvector support can replace the JSON embedding scan behind the same
service boundary.
