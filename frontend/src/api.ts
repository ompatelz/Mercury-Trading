import type {
  CampaignDashboard,
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
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
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

export async function listDatasetCatalog(): Promise<DatasetCatalogItem[]> {
  const datasets = await getJson<Dataset[]>("/datasets");
  return Promise.all(
    datasets.map(async (dataset) => ({
      ...dataset,
      versions: await getJson<DatasetVersion[]>(`/datasets/${dataset.id}/versions`)
    }))
  );
}
