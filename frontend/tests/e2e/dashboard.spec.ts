import { expect, test } from "@playwright/test";

test("shows the dark guided workspace and lets a user select a real experiment", async ({
  page
}) => {
  await page.route("**/dashboard/overview", async (route) => {
    await route.fulfill({
      json: {
        metrics: [{ label: "Experiments Run", value: 1 }],
        recent_activity: [],
        system_health: [{ component: "API", status: "ok", detail: "Dashboard API reachable" }]
      }
    });
  });
  await page.route("**/dashboard/experiments?**", async (route) => {
    await route.fulfill({
      json: {
        items: [
          {
            id: "exp-1",
            strategy_name: "moving_average_crossover",
            symbol: "MSFT",
            status: "completed",
            start_date: "2024-01-01",
            end_date: "2024-02-01",
            created_at: "2024-02-01T00:00:00Z",
            metrics: { sharpe_ratio: 1.2, max_drawdown: -0.05 },
            regime_robustness: {},
            risk_flags: []
          }
        ],
        total: 1,
        limit: 50,
        offset: 0
      }
    });
  });
  await page.route("**/dashboard/experiments/exp-1", async (route) => {
    await route.fulfill({
      json: {
        experiment: {
          id: "exp-1",
          strategy_name: "moving_average_crossover",
          symbol: "MSFT",
          status: "completed",
          start_date: "2024-01-01",
          end_date: "2024-02-01",
          created_at: "2024-02-01T00:00:00Z",
          metrics: { sharpe_ratio: 1.2, max_drawdown: -0.05 },
          regime_robustness: {},
          risk_flags: []
        },
        parameters: {},
        transaction_cost_bps: 1,
        slippage_bps: 0,
        research_context: { hypothesis: "trend" },
        performance: { sharpe_ratio: 1.2, max_drawdown: -0.05 },
        regime_performance: { "Bull / Low Vol": { sharpe_ratio: 1.2, max_drawdown: -0.05 } },
        regime_weaknesses: [],
        memory_lessons: [],
        trades: [{ timestamp: "2024-01-02T00:00:00Z", side: "BUY", price: 100, quantity: 10 }]
      }
    });
  });
  await page.route("**/experiments/exp-1/report**", async (route) => {
    await route.fulfill({
      json: {
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
      }
    });
  });
  await page.route("**/dashboard/strategies/strategy-1/lineage", async (route) => {
    await route.fulfill({
      json: {
        root_strategy_id: "strategy-1",
        evolution_run_id: "run-1",
        nodes: [
          {
            id: "strategy-1",
            parent_strategy_ids: [],
            generation: 0,
            fitness: { score: 75 },
            status: "evaluated",
            mutation_type: null,
            changed_fields: [],
            promotion_status: "promote",
            rejection_reason: null
          }
        ],
        edges: []
      }
    });
  });

  await page.goto("/");
  await expect(page.getByText("Turn an idea into")).toBeVisible();
  await expect(page.getByText("How Mercury works")).toBeVisible();
  await expect(page.getByText("Learn through examples")).toBeVisible();
  await expect(page.getByText("Moving Average Crossover")).toBeVisible();
  await expect(page.getByRole("button", { name: "Reproduce this run" })).toBeVisible();
});
