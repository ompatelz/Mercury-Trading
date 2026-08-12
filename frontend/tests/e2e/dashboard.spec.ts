import { expect, test } from "@playwright/test";

test("opens an experiment and shows metrics, chart areas, regime state, and lineage", async ({
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
  await expect(page.getByText("moving_average_crossover")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Performance", exact: true })).toBeVisible();
  await expect(page.getByText("Regime Performance")).toBeVisible();
  await expect(page.getByTestId("regime-weaknesses")).toContainText(
    "No persisted weakness flags"
  );

  await page.getByLabel("Strategy candidate id").fill("strategy-1");
  await page.getByRole("button", { name: "Load" }).first().click();
  await expect(page.getByTestId("strategy-lineage")).toContainText("promote");
});
