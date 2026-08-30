# Reliability and Recovery

Mercury's campaign worker uses durable database jobs and remains PAPER-only.
Recovery is conservative: it restores missing work, but never invents a new
experiment or treats a failed research result as successful.

## Worker failures and stale leases

Workers lease one eligible campaign job at a time.  A heartbeat marks active
work.  At worker startup, jobs with an expired heartbeat are changed to
`RETRYING` only for transient failures and only while their configured attempt
budget remains.  Retry delay is bounded exponential backoff.

## Interrupted campaigns

At startup, the worker also scans `queued` and `running` campaigns.  If a
planned experiment has no durable job at all—such as after a process failure
between planning and submission—it recreates the same idempotency-keyed job.
The unique campaign/job and campaign/experiment constraints prevent duplicate
jobs or experiments.  Existing `FAILED`, `RUNNING`, `RETRYING`, and completed
jobs are never replaced by this recovery path.

## Failure policy

Connection, timeout, and database operational errors are transient and may be
retried within the job budget.  Invalid job payloads and other deterministic
errors fail visibly without a retry loop.  A campaign with an exhausted job
failure remains failed for investigation; recovery does not silently continue
research under compromised correctness assumptions.

Market-feed reconnect and explicit model fallback are handled at their own
controlled boundaries.  They do not grant permission for live execution:
Mercury remains PAPER-only.
