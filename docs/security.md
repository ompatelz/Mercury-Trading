# Security Hardening

Mercury is a bounded, PAPER-only research system.  This document describes the
practical controls currently enforced and their limits; it does not claim that
Mercury provides an enterprise identity or secrets-management platform.

## Configuration and secrets

- Runtime settings are read from environment variables or an untracked `.env`.
- `.env` files, data directories, virtual environments, and build output are
  excluded from version control and the Docker build context.
- Docker Compose requires `POSTGRES_PASSWORD` from the environment; use
  `.env.example` only as a local template and replace its placeholder.
- CI rejects committed `.env` files and scans tracked content for private keys
  and common GitHub/OpenAI token formats.

## API boundary

- HTTP responses use `no-store`, `nosniff`, `no-referrer`, and `DENY` framing
  headers.
- API documentation is available only when `DEBUG=true`.
- Requests declaring a body larger than `MAX_REQUEST_BODY_BYTES` (1 MiB by
  default) receive HTTP 413 before route processing.
- Unexpected failures return only `internal server error`; no exception text,
  connection string, or credential value is returned to clients.

## Execution and strategy safety

`EXECUTION_MODE` accepts only `PAPER`.  The strategy DSL is a strict typed
language: it accepts indicators and comparisons, not Python code, filesystem
paths, network requests, imports, or arbitrary expressions.  Its compiler
builds Polars expressions solely from validated indicator names, and the
existing resource limits bound data volume and rule complexity.

## Containers and dependencies

The application and worker images run as an unprivileged `mercury` user.  CI
audits installed Python dependencies with `pip-audit`.  Compose credentials are
for local development only; deployers must provide a dedicated database role
with the minimum privileges required by Mercury.
