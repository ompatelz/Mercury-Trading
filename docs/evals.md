# Evals and Controlled Promotion

Mercury evals measure whether an agent or workflow version improves research
behavior. Normal CI uses deterministic benchmark tasks and local scoring.

The default research-agent benchmark checks:

- valid strategy generation
- structured output behavior
- invalid strategy or look-ahead-bias detection
- overfit strategy critique

Eval runs store the benchmark version, immutable workflow manifest, task input,
output, deterministic component scores, failures, latency, token usage, and
cost. The CI executor is deterministic; a real-model executor may be used
separately only with the same fixtures and stored model/judge metadata.

Each `WorkflowExperiment` runs a named baseline and challenger on the same
suite. Candidate changes are configuration or prompt-manifest changes only;
they never rewrite Mercury source. Candidate workflow versions capture the
hypothesis agent, strategy-generation agent, critic, retrieval configuration,
orchestrator, prompts, model parameters, tools, and workflow controls.

Promotion is a two-stage process: the experiment makes a `PROMOTED` or
`REJECTED` evidence decision, then `POST /evals/candidates/{id}/promote` may
make an eligible candidate the active champion. The endpoint refuses candidates
without a passing experiment, which makes rollback a normal version selection.

Candidate workflow versions are compared against a baseline with explicit rules:

```text
task_success_rate must not regress
invalid_strategy_rejection_rate must not regress
average latency must stay within threshold
cost must stay within threshold
critical benchmark cases must not regress
```

The initial suite covers valid momentum and mean-reversion generation, invalid
strategy rejection, look-ahead detection, overfitting detection, failed-run
critique, memory relevance, and next-experiment selection. The no-look-ahead,
invalid strategy, and structured momentum cases are critical. A direct
memory-on versus memory-off experiment uses the same memory-retrieval fixture;
Mercury does not infer benefit from retrieval merely being enabled.

LLM judging is intentionally absent from the normal suite. If needed for a
non-deterministic quality dimension, the judge must have a versioned rubric and
prompt, structured per-criterion scores, recorded model metadata, and a
consistency test; it cannot be the primary promotion criterion.
