# Distributed Research Workers

Mercury runs research through a durable PostgreSQL job queue. This deliberately
avoids Redis/Celery: the current scale is a small worker pool, and keeping the
queue beside campaign and experiment records makes state transactional and auditable.

```text
CampaignService -> campaign_jobs -> independent workers -> experiments/results
       |                                               -> campaign finalization
       +-> chooses candidates and owns state transitions
```

## Lifecycle and delivery

Jobs use `QUEUED`, `RUNNING`, `RETRYING`, `SUCCEEDED`, `FAILED`, and `CANCELLED`.
Payloads are structured JSON with a `version`; the initial job type is
`RUN_BACKTEST`. A unique `(campaign_id, idempotency_key)` constraint prevents
duplicate submission. PostgreSQL workers claim work by priority with `FOR UPDATE
SKIP LOCKED`, commit that lease, then execute backtests in a separate transaction.
Delivery is at-least-once, so completed campaign experiments are idempotent.

Claims record worker ID, attempt, timestamps, and heartbeat. Workers recover
expired `RUNNING` leases with bounded exponential backoff. Only transient
database/connection/timeout failures retry; validation and malformed requests
fail immediately. Retry history, error type, and error message remain persisted.

Cancellation is durable: queued work is cancelled immediately, while running work
receives a cooperative request checked before and after the execution handler.

## Local operation

```bash
docker compose up --build
python scripts/run_worker.py --worker-name research-a
python scripts/run_worker.py --worker-name research-b
python scripts/run_worker.py --worker-name local-worker --max-jobs 10
```

Use `GET /queue/status`, `GET /workers`, `GET /jobs/{id}`, and
`POST /jobs/{id}/cancel` for visibility. Campaign APIs remain the normal product
interface: `POST /campaigns/{id}/run` submits its candidate work.

## Adding a job type

1. Define a focused uppercase type and versioned JSON payload.
2. Submit it through `CampaignService._create_job` with an idempotency key.
3. Add an idempotent handler to `execute_claimed_job`.
4. Classify deterministic errors as non-retryable and add lifecycle tests.
5. Keep campaign/evolution decisions in `CampaignService`; workers execute only
   the defined payload.

## Budgets and benchmarking

Campaign planning caps generated candidates to experiment/trial budgets, and unique
campaign-experiment/job constraints prevent parallel delivery from creating extras.
Campaign finalization waits for all active jobs; workers never advance evolution.

`scripts/benchmark_workers.py` records wall-clock time and throughput for real,
already-queued jobs. It emits no claimed comparison numbers by default.
