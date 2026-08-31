from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardMetric(BaseModel):
    label: str
    value: int | float | str | None
    unit: str | None = None


class RecentActivityItem(BaseModel):
    id: UUID
    kind: str
    title: str
    status: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComponentHealth(BaseModel):
    component: str
    status: str
    detail: str


class DashboardOverviewResponse(BaseModel):
    metrics: list[DashboardMetric]
    recent_activity: list[RecentActivityItem]
    system_health: list[ComponentHealth]


class ModelRoutingDashboardResponse(BaseModel):
    usage: list[dict[str, object]]


class ExperimentListItem(BaseModel):
    id: UUID
    strategy_name: str
    symbol: str
    status: str
    start_date: date
    end_date: date
    created_at: datetime
    metrics: dict[str, Any]
    regime_robustness: dict[str, Any]
    campaign_id: UUID | None = None
    risk_flags: list[str] = Field(default_factory=list)
    agent_version: str | None = None
    workflow_version: str | None = None


class ExperimentListResponse(BaseModel):
    items: list[ExperimentListItem]
    total: int
    limit: int
    offset: int


class TradeChartPoint(BaseModel):
    timestamp: datetime
    side: str
    price: float
    quantity: float
    realized_pnl: float | None


class ExperimentDetailResponse(BaseModel):
    experiment: ExperimentListItem
    parameters: dict[str, Any]
    transaction_cost_bps: float
    slippage_bps: float
    research_context: dict[str, Any]
    performance: dict[str, Any]
    regime_performance: dict[str, Any]
    regime_weaknesses: list[str]
    memory_lessons: list[dict[str, Any]]
    trades: list[TradeChartPoint]


class StrategyLineageNode(BaseModel):
    id: UUID
    parent_strategy_ids: list[str]
    generation: int
    fitness: dict[str, Any]
    status: str
    mutation_type: str | None
    changed_fields: list[str]
    promotion_status: str
    rejection_reason: str | None


class StrategyLineageEdge(BaseModel):
    parent_id: str
    child_id: UUID


class StrategyLineageResponse(BaseModel):
    root_strategy_id: UUID
    evolution_run_id: UUID
    nodes: list[StrategyLineageNode]
    edges: list[StrategyLineageEdge]


class StrategyComparisonResponse(BaseModel):
    champion_id: UUID
    challenger_id: UUID
    metrics: dict[str, dict[str, Any]]
    regime_robustness: dict[str, Any]
    overfitting_flags: list[str]
    decision: str
    reason: str
    promotion_criteria: dict[str, Any]


class CampaignDashboardResponse(BaseModel):
    id: UUID
    objective: str
    status: str
    constraints: dict[str, Any]
    budget: dict[str, Any]
    budget_used: dict[str, Any]
    rounds_completed: int
    hypotheses_explored: int
    experiment_count: int
    rejected_strategy_count: int
    top_candidates: list[dict[str, Any]]
    current_best_candidate: dict[str, Any] | None
    stopping_condition: dict[str, Any]
    progress: list[dict[str, Any]]
    portfolios: list[dict[str, Any]] = Field(default_factory=list)


class PaperTradingAnalyticsResponse(BaseModel):
    """Read-only aggregate execution costs and outcomes for a PAPER replay."""

    order_count: int
    filled_order_count: int
    rejected_order_count: int
    fill_count: int
    fill_rate: float | None
    total_notional: float
    total_fees: float
    total_slippage_cost: float


class PaperTradingDashboardResponse(BaseModel):
    id: UUID
    strategy_name: str
    symbol: str
    interval: str
    execution_mode: str
    status: str
    cash: float | None
    equity: float | None
    pnl: float | None
    positions: dict[str, Any]
    metrics: dict[str, Any]
    recent_orders: list[dict[str, Any]]
    recent_fills: list[dict[str, Any]]
    rejected_orders: list[dict[str, Any]]
    analytics: PaperTradingAnalyticsResponse
    system_health: list[ComponentHealth]
