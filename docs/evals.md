# Evals and Promotion

Mercury evals measure whether an agent or workflow version improves research
behavior. Normal CI uses deterministic benchmark tasks and local scoring.

The default research-agent benchmark checks:

- valid strategy generation
- structured output behavior
- invalid strategy or look-ahead-bias detection
- overfit strategy critique

Eval runs store aggregate metrics and per-task results. Candidate workflow
versions are compared against a baseline with explicit promotion rules:

```text
task_success_rate must not regress
invalid_strategy_rejection_rate must not regress
average latency must stay within threshold
```

The result is stored as a `version_comparisons` record with metric differences,
decision, and reason. This keeps self-improvement auditable.
