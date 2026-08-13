export type DashboardMetric = {
  label: string;
  value: number | string | null;
  unit?: string | null;
};

export type ComponentHealth = {
  component: string;
  status: string;
  detail: string;
};

export type RecentActivityItem = {
  id: string;
  kind: string;
  title: string;
  status: string;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type DashboardOverview = {
  metrics: DashboardMetric[];
  recent_activity: RecentActivityItem[];
  system_health: ComponentHealth[];
};

export type ExperimentListItem = {
  id: string;
  strategy_name: string;
  symbol: string;
  status: string;
  start_date: string;
  end_date: string;
  created_at: string;
  metrics: Record<string, unknown>;
  regime_robustness: Record<string, unknown>;
  campaign_id?: string | null;
  risk_flags: string[];
  agent_version?: string | null;
  workflow_version?: string | null;
};

export type ExperimentList = {
  items: ExperimentListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type TradePoint = {
  timestamp: string;
  side: string;
  price: number;
  quantity: number;
  realized_pnl?: number | null;
};

export type ExperimentDetail = {
  experiment: ExperimentListItem;
  parameters: Record<string, unknown>;
  transaction_cost_bps: number;
  slippage_bps: number;
  research_context: Record<string, unknown>;
  performance: Record<string, unknown>;
  regime_performance: Record<string, Record<string, unknown>>;
  regime_weaknesses: string[];
  memory_lessons: Array<Record<string, unknown>>;
  trades: TradePoint[];
};

export type ResearchArtifact = {
  id: string;
  artifact_type: string;
  experiment_id?: string | null;
  campaign_id?: string | null;
  title: string;
  hypothesis?: string | null;
  measured_results: Record<string, unknown>;
  interpretation: Record<string, unknown>;
  reproducibility_metadata: Record<string, unknown>;
  charts: {
    equity_curve?: Array<{ timestamp: string; equity: number }>;
    drawdown?: Array<{ timestamp: string; drawdown: number }>;
    return_distribution?: Array<{ bucket: string; count: number }>;
  };
  export_metadata: Record<string, unknown>;
  markdown_report: string;
};

export type ReproductionResult = {
  experiment_id: string;
  status: string;
  match: boolean;
  blocking_differences: string[];
  metric_comparisons: Record<
    string,
    {
      original: number;
      reproduced?: number | null;
      difference?: number | null;
      tolerance: number;
      status: string;
    }
  >;
};

export type LineageNode = {
  id: string;
  parent_strategy_ids: string[];
  generation: number;
  fitness: Record<string, unknown>;
  status: string;
  mutation_type?: string | null;
  changed_fields: string[];
  promotion_status: string;
  rejection_reason?: string | null;
};

export type Lineage = {
  root_strategy_id: string;
  evolution_run_id: string;
  nodes: LineageNode[];
  edges: Array<{ parent_id: string; child_id: string }>;
};

export type StrategyComparison = {
  champion_id: string;
  challenger_id: string;
  metrics: Record<string, Record<string, unknown>>;
  regime_robustness: Record<string, unknown>;
  overfitting_flags: string[];
  decision: string;
  reason: string;
  promotion_criteria: Record<string, unknown>;
};

export type CampaignDashboard = {
  id: string;
  objective: string;
  status: string;
  constraints: Record<string, unknown>;
  budget: Record<string, unknown>;
  budget_used: Record<string, unknown>;
  rounds_completed: number;
  hypotheses_explored: number;
  experiment_count: number;
  rejected_strategy_count: number;
  top_candidates: Array<Record<string, unknown>>;
  current_best_candidate?: Record<string, unknown> | null;
  stopping_condition: Record<string, unknown>;
  progress: Array<Record<string, unknown>>;
};

export type PaperSessionDashboard = {
  id: string;
  strategy_name: string;
  symbol: string;
  interval: string;
  execution_mode: string;
  status: string;
  cash?: number | null;
  equity?: number | null;
  pnl?: number | null;
  positions: Record<string, unknown>;
  metrics: Record<string, unknown>;
  recent_orders: Array<Record<string, unknown>>;
  recent_fills: Array<Record<string, unknown>>;
  rejected_orders: Array<Record<string, unknown>>;
  system_health: ComponentHealth[];
};
