# Research Campaigns

A research campaign is the unit of work above a single experiment. It stores the
objective, constraints, dataset notes, symbols, date range, temporal split,
budget, generated hypotheses, planned variants, rejected strategies, candidate
strategies, and final conclusions.

The campaign hierarchy is:

```text
Campaign
  -> Hypotheses
  -> Strategy families
  -> Parameter variants
  -> Campaign jobs
  -> Backtests
  -> Evaluation
  -> Rankings
  -> Portfolio evaluation
  -> Report
```

Campaign logic lives in `app/campaigns/service.py`. API routes in
`app/api/routes/campaigns.py` only validate HTTP inputs, call services, and
serialize responses.

Campaign autonomy is deliberately bounded. The service respects
`max_experiments`, `max_optimization_trials`, `max_llm_calls`, runtime, and cost
budget fields. Current deterministic campaign planning does not make live LLM
calls; it records `llm_calls` as zero.

The final test split is locked during exploration. Campaigns use train,
validation, and pre-test walk-forward windows for candidate scoring, then
evaluate the top final candidates on the test split once while generating the
campaign report.

Campaigns can also request bounded strategy evolution through constraints:

```json
{
  "constraints": {
    "enable_evolution": true,
    "evolution_generations": 1,
    "memory_conditioned_evolution": true
  }
}
```

The campaign service remains the orchestrator. It chooses valid actions from
hypothesis generation, parameter optimization, mutation, compatible crossover,
and portfolio combination based on campaign state and budget. The LLM does not
directly control that state machine.
