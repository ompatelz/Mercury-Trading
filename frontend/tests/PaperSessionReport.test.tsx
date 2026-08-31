import { describe, expect, it } from "vitest";
import { buildPaperSessionReport } from "../src/components/PaperSessionReport";

const session = { id: "paper/session 1", strategy_name: "moving_average", symbol: "MSFT", interval: "1d", execution_mode: "PAPER", status: "COMPLETED", cash: 10000, equity: 10120, pnl: 120, positions: {}, metrics: {}, system_health: [], analytics: { order_count: 2, filled_order_count: 1, rejected_order_count: 1, fill_count: 1, fill_rate: 0.5, total_notional: 1200, total_fees: 1.2, total_slippage_cost: 0.3 }, recent_fills: [{ id: "fill-1", order_id: "order-1", strategy_id: "strategy", symbol: "MSFT", side: "BUY", quantity: 10, price: 120, fees: 1.2, slippage_cost: 0.3, timestamp: "2024-01-02T00:00:00Z" }], recent_orders: [{ id: "order-2", strategy_id: "strategy", symbol: "MSFT", side: "SELL", quantity: 10, status: "REJECTED", created_at: "2024-01-03T00:00:00Z", rejection_reason: "Risk limit" }], rejected_orders: [] };

describe("buildPaperSessionReport", () => {
  it("uses persisted PAPER data and explicitly prevents an execution interpretation", () => {
    const report = buildPaperSessionReport(session, [{ sequence: 1, timestamp: "2024-01-02T00:00:00Z", cash: 10000, equity: 10120, realized_pnl: 100, unrealized_pnl: 20, exposure: 1200, transaction_costs: 1.5 }]);
    expect(report).toContain("PAPER-only and read-only");
    expect(report).toContain("cannot create, modify, replay, or transmit an order");
    expect(report).toContain("Total fees: $1.20");
    expect(report).toContain("reason: Risk limit");
    expect(report).toContain("#1 | 2024-01-02T00:00:00.000Z | equity $10120.00");
  });

  it("states when persisted history does not exist instead of inventing it", () => {
    expect(buildPaperSessionReport(session, [])).toContain("No performance timeline is shown because no persisted portfolio snapshots were recorded.");
  });
});
