import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";

const overview = {
  metrics: [{ label: "Experiments Run", value: 2 }],
  recent_activity: [],
  system_health: [{ component: "API", status: "ok", detail: "Dashboard API reachable" }]
};

const experiment = {
  id: "exp-1",
  strategy_name: "moving_average_crossover",
  symbol: "MSFT",
  status: "completed",
  start_date: "2024-01-01",
  end_date: "2024-02-01",
  created_at: "2024-02-01T00:00:00Z",
  metrics: { sharpe_ratio: 1.2, max_drawdown: -0.05 },
  regime_robustness: {},
  campaign_id: null,
  risk_flags: [],
  agent_version: null,
  workflow_version: null
};

const detail = {
  experiment,
  parameters: { short_window: 2, long_window: 5 },
  transaction_cost_bps: 1,
  slippage_bps: 0,
  research_context: { hypothesis: "trend" },
  performance: { sharpe_ratio: 1.2, max_drawdown: -0.05 },
  regime_performance: { "Bull / Low Vol": { sharpe_ratio: 1.2, max_drawdown: -0.05 } },
  regime_weaknesses: [],
  memory_lessons: [],
  trades: [{ timestamp: "2024-01-02T00:00:00Z", side: "BUY", price: 100, quantity: 10 }]
};

const report = {
  id: "artifact-1",
  artifact_type: "experiment",
  experiment_id: "exp-1",
  campaign_id: null,
  title: "Experiment Report",
  hypothesis: "trend",
  measured_results: { sharpe_ratio: 1.2, number_of_trades: 1 },
  interpretation: { performance: "Sharpe was measured as 1.2" },
  reproducibility_metadata: { configuration_fingerprint: "abc" },
  charts: {
    equity_curve: [{ timestamp: "2024-01-02T00:00:00Z", equity: 10000 }],
    drawdown: [{ timestamp: "2024-01-02T00:00:00Z", drawdown: 0 }],
    return_distribution: [{ bucket: "0% to 1%", count: 1 }]
  },
  export_metadata: { formats: ["json", "markdown"] },
  markdown_report: "# Experiment Report"
};

const dataset = {
  id: "ds-1",
  name: "MSFT_1d"
};

const datasetVersion = {
  id: "dv-1",
  dataset_id: "ds-1",
  version: 1,
  symbols: ["MSFT"],
  provider: "market_bars_legacy_snapshot",
  frequency: "1d",
  start_timestamp: "2024-01-01T00:00:00Z",
  end_timestamp: "2024-02-01T00:00:00Z",
  schema_version: "market-bars-v1",
  row_count: 15,
  checksum: "abcdef1234567890",
  adjustment_policy: "unadjusted",
  quality_report: { valid: true, issues: [] }
};

const decision = {
  id: "decision-1",
  decision_type: "WORKFLOW_REJECTION",
  outcome: "REJECTED",
  actor: "EvalService",
  reason: "Candidate failed promotion rules",
  campaign_id: null,
  experiment_id: null,
  strategy_id: null,
  workflow_experiment_id: "workflow-exp-1",
  correlation_id: "workflow-exp-1",
  inputs: {},
  metrics: {},
  alternatives: [],
  provenance: {},
  versions: {},
  content_hash: "abcdef1234567890",
  created_at: "2024-02-01T00:00:00Z",
  rules: [
    {
      rule: "TASK_SUCCESS_DELTA",
      rule_version: "v1",
      threshold: 0,
      observed_value: -0.5,
      passed: false,
      detail: null
    }
  ],
  integrity: { verified: true, content_hash: "abcdef1234567890" }
};

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url.includes("/dashboard/overview")) return ok(overview);
        if (url.includes("/market-data/ingest")) return ok({ symbol: "MSFT", interval: "1d", rows_fetched: 252, rows_inserted: 252 });
        if (url.includes("/research/experiments") && init?.method === "POST") return ok({ id: "research-1", objective: "Test trend behavior", symbol: "MSFT", start_date: "2024-01-01", end_date: "2024-02-01", interval: "1d", status: "completed", backtest_experiment_id: "exp-2", hypothesis: { hypothesis: "A trend hypothesis" }, strategy: { strategy: "moving_average_crossover", parameters: { fast_window: 2, slow_window: 3 } }, metrics: { sharpe_ratio: 1.2 }, evaluation: { risk_findings: ["Review drawdown"] }, critique: { suggested_next_experiment: "Test more symbols." }, report: { conclusion: "Initial result only.", measured_facts: ["Sharpe ratio = 1.2"], risk_findings: ["Single symbol"] }, workflow_metadata: { workflow_run_id: "trace-1", node_durations_ms: { hypothesis: 12 }, retrieved_memory_count: 0 } });
        if (url.includes("/research/experiments")) return ok([]);
        if (url.includes("/paper-trading/sessions")) return ok([]);
        if (url.includes("/dashboard/evals")) return ok({ experiments: [] });
        if (url.endsWith("/decisions")) return ok([decision]);
        if (url.includes("/datasets/ds-1/versions")) return ok([datasetVersion]);
        if (url.endsWith("/datasets")) return ok([dataset]);
        if (url.includes("/dashboard/experiments/exp-1")) return ok(detail);
        if (url.includes("/experiments/exp-1/report")) return ok(report);
        if (url.includes("/dashboard/experiments")) {
          return ok({ items: [experiment], total: 1, limit: 50, offset: 0 });
        }
        return ok({});
      })
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads the guided paper-only workspace with live research data", async () => {
    render(<App />);

    expect(await screen.findByText("Turn an idea into")).toBeInTheDocument();
    expect(await screen.findByText("How Mercury works")).toBeInTheDocument();
    expect(await screen.findByText("Learn through examples")).toBeInTheDocument();
    expect((await screen.findAllByText("Moving Average Crossover")).length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.getByText("MSFT_1d")).toBeInTheDocument());
    expect(await screen.findByText("Workflow Rejection")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reproduce this run" })).toBeInTheDocument();
  });

  it("ingests price data before running the editable research brief", async () => {
    const fetchMock = vi.mocked(fetch);
    render(<App />);

    await screen.findByText("Ask Mercury");
    fireEvent.change(screen.getByLabelText("What do you want to test?"), { target: { value: "Test trend behavior with deterministic costs and a reviewable evidence trail." } });
    fireEvent.click(screen.getByRole("button", { name: "Send to Mercury" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/market-data/ingest",
      expect.objectContaining({ method: "POST" })
    ));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/research/experiments",
      expect.objectContaining({ method: "POST" })
    ));
    const ingestCall = fetchMock.mock.calls.findIndex(([url]) => String(url).includes("/market-data/ingest"));
    const researchCall = fetchMock.mock.calls.findIndex(
      ([url, init]) => String(url).includes("/research/experiments") && init?.method === "POST"
    );
    expect(ingestCall).toBeLessThan(researchCall);
    await screen.findByText("A trend hypothesis");
  });

  it("keeps a local conversation draft and can start a fresh one without deleting research records", async () => {
    render(<App />);

    await screen.findByText("Ask Mercury");
    fireEvent.change(screen.getByLabelText("What do you want to test?"), { target: { value: "Test trend behavior with deterministic costs and a reviewable evidence trail." } });
    fireEvent.click(screen.getByRole("button", { name: "Send to Mercury" }));

    expect(await screen.findByText("1 research turn")).toBeInTheDocument();
    expect(window.localStorage.getItem("mercury.research-conversation.v1")).toContain("Test trend behavior");

    fireEvent.click(screen.getByRole("button", { name: "Start a new research conversation" }));

    expect(screen.getByText("New conversation")).toBeInTheDocument();
    expect(screen.queryByText("A trend hypothesis")).not.toBeInTheDocument();
    expect(screen.getByLabelText("What do you want to test?")).toHaveValue("Test whether a simple moving-average trend strategy has a repeatable, risk-aware result.");
  });
});

function ok(data: unknown) {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(data)
  });
}
