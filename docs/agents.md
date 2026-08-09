# Agents and Versions

Mercury tracks which system produced each research experiment.

The default records are:

- `research_agent:v1`
- `research_workflow:v1`
- `moving_average_backtester:v1`

Research experiment metadata stores model, prompt versions, workflow version,
node durations, tool call counts, and retrieved memory summaries. This makes a
run reproducible enough to compare against future candidate versions.

Current model behavior is deterministic through `RuleBasedResearchModelClient`.
Live LLM providers should be added behind the same protocol and evaluated
against the deterministic benchmark before being promoted.
