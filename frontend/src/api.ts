import type {
  CampaignDashboard,
  Decision,
  Dataset,
  DatasetCatalogItem,
  DatasetVersion,
  DashboardOverview,
  ExperimentDetail,
  ExperimentList,
  Lineage,
  PaperSessionDashboard,
  ReproductionResult,
  ResearchArtifact,
  StrategyComparison,
  WorkflowEvalDashboard
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw await apiError(response);
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if (!response.ok) {
    throw await apiError(response);
  }
  return (await response.json()) as T;
}

export function getOverview(): Promise<DashboardOverview> {
  return getJson("/dashboard/overview");
}

export function listExperiments(query: URLSearchParams): Promise<ExperimentList> {
  return getJson(`/dashboard/experiments?${query.toString()}`);
}

export function getExperiment(id: string): Promise<ExperimentDetail> {
  return getJson(`/dashboard/experiments/${id}`);
}

export function getExperimentReport(id: string): Promise<ResearchArtifact> {
  return getJson(`/experiments/${id}/report`);
}

export function reproduceExperiment(id: string): Promise<ReproductionResult> {
  return postJson(`/experiments/${id}/reproduce`);
}

async function apiError(response: Response): Promise<Error> {
  const fallback = `${response.status} ${response.statusText}`;
  try {
    const payload = (await response.json()) as { detail?: string | Array<{ msg?: string }> };
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join("; ")
      : payload.detail;
    return new Error(detail || fallback);
  } catch {
    return new Error(fallback);
  }
}

export type ResearchRunRequest = {
  objective: string;
  symbol: string;
  start_date: string;
  end_date: string;
  interval: string;
  initial_capital: number;
  transaction_cost_bps: number;
  slippage_bps: number;
  execution_engine: string;
};

export type ResearchRunResponse = {
  id: string;
  objective: string;
  symbol: string;
  start_date: string;
  end_date: string;
  interval: string;
  status: string;
  backtest_experiment_id: string | null;
  hypothesis: { hypothesis?: string; expected_behavior?: string };
  strategy: { strategy?: string; parameters?: Record<string, unknown> };
  metrics: Record<string, unknown>;
  evaluation: { interpretation?: string; risk_findings?: string[] };
  critique: { suggested_next_experiment?: string };
  report: {
    conclusion?: string;
    measured_facts?: string[];
    risk_findings?: string[];
    suggested_next_experiment?: string;
  };
  workflow_metadata: { workflow_run_id?: string; node_durations_ms?: Record<string, number>; retrieved_memory_count?: number };
};

export type MarketDataIngestRequest = {
  symbol: string;
  start: string;
  end: string;
  interval: string;
};

export type MarketDataIngestResponse = {
  symbol: string;
  interval: string;
  rows_fetched: number;
  rows_inserted: number;
};

export function ingestMarketData(request: MarketDataIngestRequest): Promise<MarketDataIngestResponse> {
  return postJson("/market-data/ingest", request);
}

export function runResearchExperiment(request: ResearchRunRequest): Promise<ResearchRunResponse> {
  return postJson("/research/experiments", request);
}

export function listResearchExperiments(): Promise<ResearchRunResponse[]> {
  return getJson("/research/experiments?limit=6");
}

export type PaperSimulationResponse = { id: string; execution_mode: string; status: string; metrics: Record<string, unknown> };

export type PaperSessionSummary = PaperSimulationResponse & { symbol: string; strategy_name: string; started_at: string };

export function listPaperSessions(): Promise<PaperSessionSummary[]> { return getJson("/paper-trading/sessions?limit=4"); }

export function startPaperSimulation(request: { symbol: string; start: string; end: string; interval: string; strategy_name: string; strategy_parameters: Record<string, number> }): Promise<PaperSimulationResponse> {
  return postJson("/paper-trading/sessions", request);
}

export function getLineage(strategyId: string): Promise<Lineage> {
  return getJson(`/dashboard/strategies/${strategyId}/lineage`);
}

export function compareStrategies(championId: string, challengerId: string): Promise<StrategyComparison> {
  const query = new URLSearchParams({ champion_id: championId, challenger_id: challengerId });
  return getJson(`/dashboard/strategies/compare?${query.toString()}`);
}

export function getCampaign(id: string): Promise<CampaignDashboard> {
  return getJson(`/dashboard/campaigns/${id}`);
}

export function getPaperSession(id: string): Promise<PaperSessionDashboard> {
  return getJson(`/dashboard/paper-trading/sessions/${id}`);
}

export function getWorkflowEvals(): Promise<WorkflowEvalDashboard> {
  return getJson("/dashboard/evals");
}

export function listDecisions(): Promise<Decision[]> {
  return getJson("/decisions");
}

export async function listDatasetCatalog(): Promise<DatasetCatalogItem[]> {
  const datasets = await getJson<Dataset[]>("/datasets");
  return Promise.all(
    datasets.map(async (dataset) => ({
      ...dataset,
      versions: await getJson<DatasetVersion[]>(`/datasets/${dataset.id}/versions`)
    }))
  );
}
