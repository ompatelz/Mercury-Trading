import {
  Activity,
  BarChart3,
  Brain,
  Database,
  FileJson,
  FlaskConical,
  GitBranch,
  LineChart,
  Repeat2,
  RefreshCw,
  Scale,
  Search
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  getCampaign,
  getExperiment,
  getExperimentReport,
  getLineage,
  getOverview,
  getPaperSession,
  getWorkflowEvals,
  listDatasetCatalog,
  listExperiments,
  reproduceExperiment
} from "./api";
import type {
  CampaignDashboard,
  DatasetCatalogItem,
  DashboardMetric,
  DashboardOverview,
  ExperimentDetail,
  ExperimentListItem,
  Lineage,
  PaperSessionDashboard,
  ReproductionResult,
  ResearchArtifact,
  WorkflowEvalDashboard
} from "./types";

type LoadState<T> =
  | { status: "idle" | "loading"; data?: T; error?: undefined }
  | { status: "ready"; data: T; error?: undefined }
  | { status: "error"; data?: T; error: string };

const money = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

export function App() {
  const [overview, setOverview] = useState<LoadState<DashboardOverview>>({ status: "loading" });
  const [experiments, setExperiments] = useState<LoadState<ExperimentListItem[]>>({
    status: "loading"
  });
  const [selectedExperimentId, setSelectedExperimentId] = useState<string | null>(null);
  const [experiment, setExperiment] = useState<LoadState<ExperimentDetail>>({ status: "idle" });
  const [report, setReport] = useState<LoadState<ResearchArtifact>>({ status: "idle" });
  const [reproduction, setReproduction] = useState<LoadState<ReproductionResult>>({
    status: "idle"
  });
  const [lineage, setLineage] = useState<LoadState<Lineage>>({ status: "idle" });
  const [campaign, setCampaign] = useState<LoadState<CampaignDashboard>>({ status: "idle" });
  const [paper, setPaper] = useState<LoadState<PaperSessionDashboard>>({ status: "idle" });
  const [workflowEvals, setWorkflowEvals] = useState<LoadState<WorkflowEvalDashboard>>({ status: "loading" });
  const [dataCatalog, setDataCatalog] = useState<LoadState<DatasetCatalogItem[]>>({
    status: "loading"
  });
  const [filters, setFilters] = useState({ symbol: "", status: "", strategy_family: "" });
  const [ids, setIds] = useState({ strategy: "", campaign: "", paper: "" });

  useEffect(() => {
    void refreshOverview();
    void refreshExperiments();
    void refreshWorkflowEvals();
    void refreshDataCatalog();
    // The initial load should not refetch while users type filters; Apply controls refresh timing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedExperimentId) {
      setExperiment({ status: "loading" });
      setReport({ status: "loading" });
      setReproduction({ status: "idle" });
      getExperiment(selectedExperimentId)
        .then((data) => setExperiment({ status: "ready", data }))
        .catch((error: Error) => setExperiment({ status: "error", error: error.message }));
      getExperimentReport(selectedExperimentId)
        .then((data) => setReport({ status: "ready", data }))
        .catch((error: Error) => setReport({ status: "error", error: error.message }));
    }
  }, [selectedExperimentId]);

  const selectedExperiment = experiment.status === "ready" ? experiment.data : null;
  const regimeRows = useMemo(() => regimeChartRows(selectedExperiment), [selectedExperiment]);
  const tradeRows = useMemo(() => tradeChartRows(selectedExperiment), [selectedExperiment]);
  const equityRows = useMemo(() => reportChartRows(report, "equity_curve"), [report]);
  const drawdownRows = useMemo(() => reportChartRows(report, "drawdown"), [report]);
  const returnRows = useMemo(() => returnDistributionRows(report), [report]);

  async function refreshOverview() {
    setOverview({ status: "loading" });
    try {
      setOverview({ status: "ready", data: await getOverview() });
    } catch (error) {
      setOverview({ status: "error", error: (error as Error).message });
    }
  }

  async function refreshExperiments() {
    setExperiments({ status: "loading" });
    const query = new URLSearchParams({ limit: "50" });
    Object.entries(filters).forEach(([key, value]) => {
      if (value.trim()) query.set(key, value.trim());
    });
    try {
      const data = await listExperiments(query);
      setExperiments({ status: "ready", data: data.items });
      if (!selectedExperimentId && data.items[0]) setSelectedExperimentId(data.items[0].id);
    } catch (error) {
      setExperiments({ status: "error", error: (error as Error).message });
    }
  }

  async function refreshWorkflowEvals() {
    setWorkflowEvals({ status: "loading" });
    try {
      const data = await getWorkflowEvals();
      setWorkflowEvals({
        status: "ready",
        data: { experiments: Array.isArray(data.experiments) ? data.experiments : [] }
      });
    } catch (error) {
      setWorkflowEvals({ status: "error", error: (error as Error).message });
    }
  }

  async function refreshDataCatalog() {
    setDataCatalog({ status: "loading" });
    try {
      setDataCatalog({ status: "ready", data: await listDatasetCatalog() });
    } catch (error) {
      setDataCatalog({ status: "error", error: (error as Error).message });
    }
  }

  async function loadLineage() {
    if (!ids.strategy.trim()) return;
    setLineage({ status: "loading" });
    try {
      setLineage({ status: "ready", data: await getLineage(ids.strategy.trim()) });
    } catch (error) {
      setLineage({ status: "error", error: (error as Error).message });
    }
  }

  async function loadCampaign() {
    if (!ids.campaign.trim()) return;
    setCampaign({ status: "loading" });
    try {
      setCampaign({ status: "ready", data: await getCampaign(ids.campaign.trim()) });
    } catch (error) {
      setCampaign({ status: "error", error: (error as Error).message });
    }
  }

  async function loadPaper() {
    if (!ids.paper.trim()) return;
    setPaper({ status: "loading" });
    try {
      setPaper({ status: "ready", data: await getPaperSession(ids.paper.trim()) });
    } catch (error) {
      setPaper({ status: "error", error: (error as Error).message });
    }
  }

  async function runReproduction() {
    if (!selectedExperimentId) return;
    setReproduction({ status: "loading" });
    try {
      setReproduction({
        status: "ready",
        data: await reproduceExperiment(selectedExperimentId)
      });
    } catch (error) {
      setReproduction({ status: "error", error: (error as Error).message });
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Mercury</p>
          <h1>Research Dashboard</h1>
        </div>
        <button className="iconButton" onClick={() => void refreshOverview()} aria-label="Refresh">
          <RefreshCw size={18} />
        </button>
      </header>

      <section className="metrics" aria-label="Dashboard metrics">
        {overview.status === "ready" ? (
          overview.data.metrics.map((metric) => (
            <article className="metric" key={metric.label}>
              <span>{metric.label}</span>
              <strong>{formatMetric(metric.value, metric.unit)}</strong>
            </article>
          ))
        ) : (
          <StateBlock state={overview.status} error={overview.error} label="overview" />
        )}
      </section>

      <section className="grid two">
        <Panel title="Experiment Explorer" icon={<Search size={17} />}>
          <div className="filters">
            <input
              aria-label="Symbol filter"
              placeholder="Symbol"
              value={filters.symbol}
              onChange={(event) => setFilters({ ...filters, symbol: event.target.value })}
            />
            <input
              aria-label="Status filter"
              placeholder="Status"
              value={filters.status}
              onChange={(event) => setFilters({ ...filters, status: event.target.value })}
            />
            <input
              aria-label="Strategy family filter"
              placeholder="Strategy family"
              value={filters.strategy_family}
              onChange={(event) =>
                setFilters({ ...filters, strategy_family: event.target.value })
              }
            />
            <button onClick={() => void refreshExperiments()}>Apply</button>
          </div>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Symbol</th>
                  <th>Status</th>
                  <th>Sharpe</th>
                  <th>Drawdown</th>
                </tr>
              </thead>
              <tbody>
                {experiments.status === "ready" &&
                  experiments.data.map((item) => (
                    <tr
                      key={item.id}
                      className={item.id === selectedExperimentId ? "selected" : ""}
                      onClick={() => setSelectedExperimentId(item.id)}
                    >
                      <td>{item.strategy_name}</td>
                      <td>{item.symbol}</td>
                      <td>{item.status}</td>
                      <td>{numberValue(item.metrics.sharpe_ratio)}</td>
                      <td>{numberValue(item.metrics.max_drawdown)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <StateBlock state={experiments.status} error={experiments.error} label="experiments" />
        </Panel>

        <Panel title="System Health" icon={<Activity size={17} />}>
          <div className="healthList">
            {overview.status === "ready" &&
              overview.data.system_health.map((item) => (
                <div className="health" key={item.component}>
                  <span className={`dot ${item.status.toLowerCase()}`} />
                  <div>
                    <strong>{item.component}</strong>
                    <p>{item.detail}</p>
                  </div>
                </div>
              ))}
          </div>
          <h3>Recent Activity</h3>
          <div className="activityList">
            {overview.status === "ready" &&
              overview.data.recent_activity.map((item) => (
                <div className="activityItem" key={item.id}>
                  <span>{item.kind}</span>
                  <strong>{item.title}</strong>
                  <small>{item.status}</small>
                </div>
              ))}
          </div>
        </Panel>
      </section>

      <section className="grid">
        <Panel title="Research Data" icon={<Database size={17} />}>
          {dataCatalog.status === "ready" ? (
            dataCatalog.data.length ? (
              <div className="tableWrap dataCatalog" data-testid="research-data-catalog">
                <table>
                  <thead>
                    <tr>
                      <th>Dataset</th>
                      <th>Version</th>
                      <th>Symbols</th>
                      <th>Rows</th>
                      <th>Policy</th>
                      <th>Quality</th>
                      <th>Checksum</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dataCatalog.data.flatMap((dataset) =>
                      dataset.versions.map((version) => (
                        <tr key={version.id}>
                          <td>{dataset.name}</td>
                          <td>v{version.version}</td>
                          <td>{version.symbols.join(", ")}</td>
                          <td>{version.row_count}</td>
                          <td>{version.adjustment_policy}</td>
                          <td>{version.quality_report.valid === false ? "failed" : "passed"}</td>
                          <td>{version.checksum.slice(0, 12)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="empty">No immutable datasets have been created yet.</p>
            )
          ) : (
            <StateBlock state={dataCatalog.status} error={dataCatalog.error} label="research data" />
          )}
        </Panel>
      </section>

      <section className="grid two">
        <Panel title="Experiment Detail" icon={<FlaskConical size={17} />}>
          {selectedExperiment ? (
            <>
              <div className="split">
                <MetricColumn title="Research Context" value={selectedExperiment.research_context} />
                <MetricColumn title="Performance" value={selectedExperiment.performance} />
              </div>
              <div className="chartGrid">
                <ChartFrame title="Trades">
                  <ResponsiveContainer width="100%" height={220}>
                    <RechartsLineChart data={tradeRows}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="label" />
                      <YAxis />
                      <Tooltip />
                      <Line dataKey="price" stroke="#1f7a8c" dot={false} />
                    </RechartsLineChart>
                  </ResponsiveContainer>
                </ChartFrame>
                <ChartFrame title="Regime Performance">
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={regimeRows}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="regime" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="sharpe" fill="#3d5a80" />
                      <Bar dataKey="drawdown" fill="#c44536" />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartFrame>
              </div>
              <div className="weaknesses" data-testid="regime-weaknesses">
                <strong>Regime Weaknesses</strong>
                <span>
                  {selectedExperiment.regime_weaknesses.length
                    ? selectedExperiment.regime_weaknesses.join(", ")
                    : "No persisted weakness flags"}
                </span>
              </div>
            </>
          ) : (
            <StateBlock state={experiment.status} error={experiment.error} label="experiment detail" />
          )}
        </Panel>

        <Panel title="Research Report" icon={<FileJson size={17} />}>
          {report.status === "ready" ? (
            <>
              <div className="reportActions">
                <a href={`/experiments/${report.data.experiment_id}/report?format=json`}>JSON</a>
                <a href={`/experiments/${report.data.experiment_id}/report?format=markdown`}>
                  Markdown
                </a>
                <button onClick={() => void runReproduction()}>
                  <Repeat2 size={16} />
                  Reproduce
                </button>
              </div>
              <div className="split">
                <MetricColumn title="Measured Result" value={report.data.measured_results} />
                <MetricColumn title="Interpretation" value={report.data.interpretation} />
              </div>
              <MetricColumn
                title="Reproducibility"
                value={report.data.reproducibility_metadata}
              />
              {reproduction.status === "ready" ? (
                <div className={`reproduction ${reproduction.data.match ? "match" : "mismatch"}`}>
                  <strong>{reproduction.data.status}</strong>
                  <span>
                    {reproduction.data.blocking_differences.length
                      ? reproduction.data.blocking_differences.join(", ")
                      : "metrics and fingerprints match"}
                  </span>
                </div>
              ) : (
                <StateBlock
                  state={reproduction.status}
                  error={reproduction.error}
                  label="reproduction"
                />
              )}
            </>
          ) : (
            <StateBlock state={report.status} error={report.error} label="research report" />
          )}
        </Panel>
      </section>

      <section className="grid two">
        <Panel title="Research Charts" icon={<LineChart size={17} />}>
          <div className="chartGrid">
            <ChartFrame title="Equity Curve">
              <ResponsiveContainer width="100%" height={220}>
                <RechartsLineChart data={equityRows}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" />
                  <YAxis />
                  <Tooltip />
                  <Line dataKey="equity" stroke="#1f7a8c" dot={false} />
                </RechartsLineChart>
              </ResponsiveContainer>
            </ChartFrame>
            <ChartFrame title="Drawdown">
              <ResponsiveContainer width="100%" height={220}>
                <RechartsLineChart data={drawdownRows}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" />
                  <YAxis />
                  <Tooltip />
                  <Line dataKey="drawdown" stroke="#c44536" dot={false} />
                </RechartsLineChart>
              </ResponsiveContainer>
            </ChartFrame>
            <ChartFrame title="Return Distribution">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={returnRows}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="bucket" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="count" fill="#3d5a80" />
                </BarChart>
              </ResponsiveContainer>
            </ChartFrame>
          </div>
        </Panel>

        <Panel title="Memory & Learning" icon={<Brain size={17} />}>
          {selectedExperiment?.memory_lessons.length ? (
            selectedExperiment.memory_lessons.map((lesson) => (
              <article className="lesson" key={String(lesson.id)}>
                <strong>{String(lesson.hypothesis)}</strong>
                <p>{String(lesson.critic_summary)}</p>
              </article>
            ))
          ) : (
            <p className="empty">No memory lessons linked to the selected experiment.</p>
          )}
        </Panel>
      </section>

      <section className="grid three">
        <LookupPanel
          title="Strategy Evolution"
          icon={<GitBranch size={17} />}
          label="Strategy candidate id"
          value={ids.strategy}
          onChange={(value) => setIds({ ...ids, strategy: value })}
          onLoad={() => void loadLineage()}
        >
          {lineage.status === "ready" ? (
            <div className="lineage" data-testid="strategy-lineage">
              {lineage.data.nodes.map((node) => (
                <div className="node" key={node.id}>
                  <strong>Gen {node.generation}</strong>
                  <span>{node.promotion_status}</span>
                  <small>{node.mutation_type ?? "seed"}</small>
                </div>
              ))}
            </div>
          ) : (
            <StateBlock state={lineage.status} error={lineage.error} label="lineage" />
          )}
        </LookupPanel>

        <LookupPanel
          title="Campaign Monitor"
          icon={<BarChart3 size={17} />}
          label="Campaign id"
          value={ids.campaign}
          onChange={(value) => setIds({ ...ids, campaign: value })}
          onLoad={() => void loadCampaign()}
        >
          {campaign.status === "ready" ? (
            <div>
              <strong>{campaign.data.objective}</strong>
              <div className="miniMetrics">
                <span>{campaign.data.experiment_count} experiments</span>
                <span>{campaign.data.rounds_completed} rounds</span>
                <span>{campaign.data.rejected_strategy_count} rejected</span>
              </div>
            </div>
          ) : (
            <StateBlock state={campaign.status} error={campaign.error} label="campaign" />
          )}
        </LookupPanel>

        <LookupPanel
          title="Paper Trading"
          icon={<Scale size={17} />}
          label="Paper session id"
          value={ids.paper}
          onChange={(value) => setIds({ ...ids, paper: value })}
          onLoad={() => void loadPaper()}
        >
          {paper.status === "ready" ? (
            <div>
              <strong>{paper.data.strategy_name}</strong>
              <div className="miniMetrics">
                <span>{paper.data.status}</span>
                <span>Equity {numberValue(paper.data.equity)}</span>
                <span>PnL {numberValue(paper.data.pnl)}</span>
              </div>
            </div>
          ) : (
            <StateBlock state={paper.status} error={paper.error} label="paper session" />
          )}
        </LookupPanel>
      </section>

      <section className="compare">
        <Panel title="Champion / Challenger" icon={<LineChart size={17} />}>
          {workflowEvals.status === "ready" ? (
            workflowEvals.data.experiments.length ? (
              workflowEvals.data.experiments.slice(0, 5).map((item) => (
                <div className="activityItem" key={item.id}>
                  <span>{item.benchmark_name}</span>
                  <strong>{item.decision}</strong>
                  <small>{item.reason}</small>
                </div>
              ))
            ) : (
              <p className="empty">No workflow challengers have been evaluated.</p>
            )
          ) : (
            <StateBlock state={workflowEvals.status} error={workflowEvals.error} label="workflow evals" />
          )}
        </Panel>
      </section>
    </main>
  );
}

function Panel({
  title,
  icon,
  children
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <header>
        {icon}
        <h2>{title}</h2>
      </header>
      {children}
    </section>
  );
}

function LookupPanel({
  title,
  icon,
  label,
  value,
  onChange,
  onLoad,
  children
}: {
  title: string;
  icon: React.ReactNode;
  label: string;
  value: string;
  onChange: (value: string) => void;
  onLoad: () => void;
  children: React.ReactNode;
}) {
  return (
    <Panel title={title} icon={icon}>
      <div className="lookup">
        <input aria-label={label} placeholder={label} value={value} onChange={(event) => onChange(event.target.value)} />
        <button onClick={onLoad}>Load</button>
      </div>
      {children}
    </Panel>
  );
}

function MetricColumn({ title, value }: { title: string; value: Record<string, unknown> }) {
  return (
    <div className="metricColumn">
      <h3>{title}</h3>
      {Object.entries(value)
        .slice(0, 8)
        .map(([key, item]) => (
          <div className="kv" key={key}>
            <span>{key.replaceAll("_", " ")}</span>
            <strong>{renderValue(item)}</strong>
          </div>
        ))}
    </div>
  );
}

function ChartFrame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="chartFrame">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

function StateBlock({ state, error, label }: { state: string; error?: string; label: string }) {
  if (state === "ready" || state === "idle") return null;
  return <p className={state === "error" ? "error" : "empty"}>{state === "error" ? error : `Loading ${label}`}</p>;
}

function regimeChartRows(detail: ExperimentDetail | null) {
  if (!detail) return [];
  return Object.entries(detail.regime_performance).map(([regime, metrics]) => ({
    regime,
    sharpe: numeric(metrics.sharpe_ratio ?? metrics.sharpe),
    drawdown: numeric(metrics.max_drawdown)
  }));
}

function tradeChartRows(detail: ExperimentDetail | null) {
  if (!detail) return [];
  return detail.trades.map((trade, index) => ({
    label: String(index + 1),
    price: trade.price,
    side: trade.side
  }));
}

function reportChartRows(
  state: LoadState<ResearchArtifact>,
  key: "equity_curve" | "drawdown"
) {
  if (state.status !== "ready") return [];
  const rows = state.data.charts[key] ?? [];
  return rows.map((row, index) => ({
    ...row,
    label: String(index + 1)
  }));
}

function returnDistributionRows(state: LoadState<ResearchArtifact>) {
  if (state.status !== "ready") return [];
  return state.data.charts.return_distribution ?? [];
}

function formatMetric(value: DashboardMetric["value"], unit?: string | null) {
  if (value === null) return "n/a";
  if (typeof value === "number") {
    return unit === "ratio" ? `${(value * 100).toFixed(1)}%` : money.format(value);
  }
  return value;
}

function numberValue(value: unknown) {
  const parsed = numeric(value);
  return parsed === null ? "n/a" : money.format(parsed);
}

function numeric(value: unknown) {
  return typeof value === "number" ? value : null;
}

function renderValue(value: unknown) {
  if (typeof value === "number") return money.format(value);
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
