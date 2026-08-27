# Model routing

Mercury routes only its defined research tasks: hypothesis and strategy generation, critique,
risk explanation, planning, extraction, memory summarization, and report writing. It is not a
generic AI gateway. Each registered model declares its provider, version, context window,
structured-output/tool support, cost estimate, enabled state, and fallback chain.

`ModelRouter` ranks only compatible enabled candidates. Its persisted decision separates measured
quality, success rate, structured-output reliability, latency penalty, and cost penalty. FAST,
BALANCED, and HIGH_QUALITY change the published weights; no opaque reputation score is used.

Benchmark evidence is task-specific. A model without evidence receives no quality credit, so it
cannot become the default merely because it is registered. Campaign callers can set max cost,
remaining cost, token, and call limits. Non-critical work can select a feasible cheaper candidate;
critical work fails rather than silently violating its quality/budget contract.

Every call is persisted with task, agent, provider/model, tokens, latency, estimated cost,
success, retries, fallback/escalation information, workflow, experiment, and campaign links.
`GET /dashboard/model-routing` exposes aggregate usage, cost, latency, success, and fallback rate.
Provider adapters remain behind the typed research-client interface and are mocked in CI. Local
models can be added through the same registry without deploying a local inference stack.
