# Workers and Jobs

Mercury uses a PostgreSQL-backed job table instead of Redis/Celery for campaign
execution. That matches the current modular monolith, keeps CI simple, and makes
job state auditable before adding distributed queue infrastructure.

Job states:

```text
queued
running
succeeded
failed
cancelled
retrying
```

Each job stores campaign ID, optional campaign experiment ID, worker name,
attempt count, start/end timestamps, error message, runtime, payload, and an
idempotency key. Duplicate job submission for the same campaign experiment is
prevented by a unique constraint.

Run a worker locally:

```bash
python scripts/run_worker.py --worker-name local-worker
```

Process a bounded batch:

```bash
python scripts/run_worker.py --worker-name local-worker --max-jobs 10
```

Docker Compose starts a `worker` service that runs the same script after
migrations. The API also exposes `POST /jobs/work` for deterministic test and
development execution.
