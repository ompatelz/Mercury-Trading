# Walk-forward production simulation

Mercury's production simulation is a deterministic historical replay of the
production decision loop. It is explicitly paper-only: each deployment creates
an existing `PaperTradingSession` with `execution_mode=PAPER`, so it can emit
simulated orders and fills but has no broker path.

## Temporal boundary

Each cycle has a research interval followed by an unseen deployment interval.
The cycle stores both dates, the frozen strategy version and parameters, the
dataset versions, and the paper session ID. Research decisions are made at the
research end date; deployment results are observed only after that boundary.
Candidate manifests may carry an eligibility date and promotion flag; selection
is deterministic and considers only candidates eligible at the research date.
Research memory has `available_from`, derived from the source experiment's end
date. Retrieval accepts `as_of` and excludes lessons created after that date.

## Lifecycle and metrics

The persisted simulation timeline records `ACTIVE` deployments, governance
decision correlation IDs, expected and realized metrics, degradation, and
flags. Aggregate metrics include research cycles, deployments, replay events,
strategy changes, kill flags, PnL, runtime, and expected-vs-realized deltas.

The timeline records `PROMOTED`, `ACTIVE`, `REPLACED`, and `RETIRED` lifecycle
events. Portfolio weights are frozen in each cycle's configuration and timeline.
Counterfactual fields are recorded after deployment and are explicitly excluded
from the selection decision.

## API

`POST /simulations` creates and runs a short deterministic replay. Read the
aggregate with `GET /simulations/{id}`, or use `/timeline`, `/deployments`, and
`/metrics` for dashboard consumers. Counterfactual evaluation must be an
after-the-fact analysis and must never modify the historical timeline.
