# Strategy lifecycle and continuous research

Mercury manages strategies as durable research records. It does not replace a strategy after a short loss streak.

```text
RESEARCHED -> VALIDATED -> PROMOTED -> ACTIVE -> MONITORED
                                            |
                          RETAIN / INVESTIGATE / DE-RISK / RETIRE
```

## Health evidence

`StrategyHealthService` stores a rolling observation rather than overwriting history. Each observation contains realized rolling return, Sharpe, volatility, drawdown, turnover, trade/sample counts, expected validation metrics, regime context, and execution-cost context.

The deterministic `strategy-health-v1` rule produces independently stored score components for return, Sharpe, drawdown, volatility, turnover, and execution quality. Flags are explicit: `PERFORMANCE_DEGRADATION`, `SHARPE_DECAY`, `DRAWDOWN_ABNORMAL`, `TURNOVER_DRIFT`, `EXECUTION_DEGRADATION`, and `REGIME_MISMATCH`.

At least three observations and ten trades are required before alpha degradation is eligible. One poor eligible window becomes `WATCH`; a second poor window with two or more alpha flags becomes `DEGRADED`. An execution-cost problem alone cannot create alpha retirement. Expected regime weakness is recorded as context and results in investigation rather than a panic replacement.

## Lifecycle actions

`HEALTHY`, `WATCH`, and `DEGRADED` are automatic evidence states. `SUSPENDED` and `RETIRED` require an explicit lifecycle transition with a reason, producing an immutable `DecisionRecord`. A suspended strategy can reactivate when objective conditions recover. A retired strategy cannot be automatically reactivated.

Portfolio integrations use the deterministic health multipliers: healthy `1.0`, watch `0.9`, degraded `0.5`, suspended/retired `0.0`. No model client can alter allocation.

## Research scheduling

Research schedules are `PERIODIC`, `EVENT_TRIGGERED`, or `HYBRID`. They store a validated `CampaignCreateRequest` template and create campaigns only through `CampaignService`, preserving its budgets, temporal splits, queue concurrency, and locked-test behavior. Trigger de-duplication is one schedule, trigger type, and day. `STRATEGY_DEGRADED` can therefore launch a challenger search without automatically replacing the current champion.

Use `POST /strategy-health/strategies/{strategy_id}/observations` to record evidence, `POST /strategy-health/schedules` to configure controlled research, and `GET /dashboard/strategies/{strategy_id}/lifecycle` for the evidence timeline.
