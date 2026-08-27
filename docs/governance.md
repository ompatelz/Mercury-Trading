# Research Governance

Mercury records research decisions as append-only provenance events. The ledger is
designed to answer four operational questions:

- What decision was made?
- Which deterministic rule checks supported it?
- Which campaign, experiment, strategy, workflow, data, and memory inputs shaped it?
- Can the stored decision be replayed and verified against its content hash?

## Decision Ledger

The core tables are:

- `decision_records`: one immutable decision event with actor, reason, outcome,
  linked entity ids, inputs, metrics, alternatives, provenance, versions, and a
  SHA-256 content hash.
- `decision_rule_evaluations`: rule-level evidence linked to a decision record.
  Rules store the rule name, rule version, threshold, observed value, pass/fail,
  and optional detail.

Decisions are created through `DecisionService.record()`. The service normalizes
rules before hashing, writes the decision and rule rows in one unit of work, and
can replay a decision with `DecisionService.explain()`. Replay recomputes the
hash from persisted fields and returns `integrity.verified`.

## Recorded Decisions

The current implementation records these decision types:

- `CAMPAIGN_PLAN`: campaign split, hypothesis, parameter-search, and budget plan.
- `CAMPAIGN_QUEUE`: planned campaign experiments queued as deterministic jobs.
- `CAMPAIGN_EXPERIMENT_ACCEPTANCE`: validation completed without persisted risk flags.
- `CAMPAIGN_EXPERIMENT_REJECTION`: validation completed with persisted risk flags.
- `CAMPAIGN_FINALIZATION`: rankings, locked test evaluations, portfolios, and final report state.
- `HUMAN_OVERRIDE`: controlled manual action, currently campaign cancellation.
- `MUTATION_SELECTION`: strategy mutation selected for deterministic evaluation.
- `STRATEGY_PROMOTION` / `STRATEGY_REJECTION`: evolution champion/challenger result.
- `WORKFLOW_PROMOTION` / `WORKFLOW_REJECTION`: workflow eval promotion gate result.

## API

Governance endpoints expose ledger data without recalculating research results:

- `GET /decisions`
- `GET /decisions/{decision_id}`
- `GET /experiments/{experiment_id}/decisions`
- `GET /campaigns/{campaign_id}/timeline`
- `GET /strategies/{strategy_id}/lineage`

The dashboard reads `GET /decisions` for the Audit / Decisions panel. Research
reports include decision summaries under `provenance.decision_audit`, including
decision ids, outcomes, content hashes, and replay integrity status.

The replay CLI prints the same explanation payload:

```powershell
.\.venv\Scripts\python scripts\explain_decision.py <decision-id>
```

## Governance Boundaries

Mercury still keeps deterministic services in charge of calculations. Agents can
propose, critique, retrieve lessons, or route work, but promotion, rejection,
ranking, risk checks, and replay evidence are persisted by backend services.

The ledger is append-only at the application level. If a decision is replaced by
a later review, the replacement should use `supersedes_id` and leave the original
row intact.

## Files To Read To Understand Mercury

Overall entry points:

- `README.md`
- `docs/architecture.md`
- `app/main.py`
- `app/db/base.py`
- `app/models/__init__.py`

Governance and audit:

- `app/models/governance.py`
- `app/governance/service.py`
- `app/api/routes/decisions.py`
- `scripts/explain_decision.py`
- `docs/governance.md`

Research campaigns and decisions:

- `app/campaigns/service.py`
- `app/campaigns/ranking.py`
- `app/campaigns/overfitting.py`
- `app/campaigns/walk_forward.py`
- `docs/campaigns.md`

Experiments, reports, and reproducibility:

- `app/experiments/service.py`
- `app/research_artifacts/service.py`
- `app/research_artifacts/fingerprints.py`
- `docs/research_artifacts.md`
- `docs/testing.md`

Workflow evals and promotion:

- `app/evals/service.py`
- `app/evals/benchmarks.py`
- `app/api/routes/evals.py`
- `docs/evals.md`

Strategy evolution and lineage:

- `app/evolution/service.py`
- `app/evolution/fitness.py`
- `app/evolution/mutation.py`
- `app/evolution/specification.py`
- `docs/evolution.md`

Data, features, and provenance:

- `app/data/service.py`
- `app/models/data.py`
- `docs/data.md`
- `docs/regimes.md`

Dashboard:

- `app/dashboard/service.py`
- `app/api/routes/dashboard.py`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`

Paper-only execution:

- `app/paper_trading/live_service.py`
- `app/paper_trading/service.py`
- `docs/paper_trading.md`
- `docs/live_execution.md`

The 10 highest-signal files for a new engineer are:

- `README.md`
- `docs/architecture.md`
- `app/main.py`
- `app/campaigns/service.py`
- `app/experiments/service.py`
- `app/research_artifacts/service.py`
- `app/governance/service.py`
- `app/evals/service.py`
- `app/evolution/service.py`
- `frontend/src/App.tsx`
