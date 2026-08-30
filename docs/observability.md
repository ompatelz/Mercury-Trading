# Observability

Mercury exposes a minimal operational telemetry surface without introducing a
runtime dependency on a tracing collector or metrics SDK.

## HTTP correlation

Every successful HTTP response contains `X-Correlation-ID`.  Send that header
on a request to preserve an upstream trace identifier; otherwise Mercury
generates a UUID.  Operators should include the identifier in incident notes
and use it to correlate proxy and application-level records.

## Metrics

`GET /metrics` returns Prometheus text exposition data with:

- `mercury_http_requests_total`, labelled by request method and response status;
- `mercury_http_request_latency_ms_total`, labelled by request method.

The registry is in-process.  It resets when the application restarts and is
not aggregated across workers.  A production Prometheus deployment must scrape
each worker (or aggregate its own view) and must not treat this endpoint as a
substitute for durable tracing or log retention.

## Readiness

`GET /readyz` performs `SELECT 1` through Mercury's configured database
session.  It returns HTTP 200 only when that probe succeeds and HTTP 503 when
the database is unavailable.  Use it for load-balancer readiness checks;
`/health` remains the lightweight liveness endpoint.

Telemetry intentionally avoids request payloads, credentials, portfolio data,
and other sensitive trading inputs.  Mercury remains PAPER-only; these
endpoints do not add any execution capability.
