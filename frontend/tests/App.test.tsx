import { render, screen, waitFor } from "@testing-library/react";
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

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/dashboard/overview")) return ok(overview);
        if (url.includes("/dashboard/evals")) return ok({ experiments: [] });
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
    vi.unstubAllGlobals();
  });

  it("loads overview, experiments, metrics, charts, and regime state", async () => {
    render(<App />);

    expect(await screen.findByText("Research Dashboard")).toBeInTheDocument();
    expect(await screen.findByText("Experiments Run")).toBeInTheDocument();
    expect(await screen.findByText("moving_average_crossover")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Performance")).toBeInTheDocument());
    expect(await screen.findByText("Measured Result")).toBeInTheDocument();
    expect(screen.getByText("Equity Curve")).toBeInTheDocument();
    expect(screen.getByText("Regime Performance")).toBeInTheDocument();
    expect(screen.getByTestId("regime-weaknesses")).toHaveTextContent(
      "No persisted weakness flags"
    );
  });
});

function ok(data: unknown) {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(data)
  });
}
