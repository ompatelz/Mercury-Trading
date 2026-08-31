import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PaperExecutionLedger } from "../src/components/PaperExecutionLedger";

afterEach(cleanup);

const session = { id: "paper-1", strategy_name: "moving_average", symbol: "MSFT", interval: "1d", execution_mode: "PAPER", status: "COMPLETED", cash: 10000, equity: 10020, pnl: 20, positions: {}, metrics: {}, system_health: [], analytics: { order_count: 2, filled_order_count: 1, rejected_order_count: 1, fill_count: 1, fill_rate: 0.5, total_notional: 1200, total_fees: 1.2, total_slippage_cost: 0.3 }, recent_fills: [{ id: "fill-1", order_id: "order-1", strategy_id: "strategy", symbol: "MSFT", side: "BUY", quantity: 10, price: 120, fees: 1.2, slippage_cost: 0.3, timestamp: "2024-01-02T00:00:00Z" }], recent_orders: [{ id: "order-1", strategy_id: "strategy", symbol: "MSFT", side: "BUY", quantity: 10, status: "FILLED", created_at: "2024-01-02T00:00:00Z", rejection_reason: null }, { id: "order-2", strategy_id: "strategy", symbol: "MSFT", side: "SELL", quantity: 10, status: "REJECTED", created_at: "2024-01-03T00:00:00Z", rejection_reason: "Risk limit" }], rejected_orders: [] };

describe("PaperExecutionLedger", () => {
  it("renders persisted paper fills, costs, and rejected-order reasons", () => {
    render(<PaperExecutionLedger session={session} />);
    expect(screen.getByRole("region", { name: "PAPER execution ledger" })).toHaveTextContent("READ-ONLY EXECUTION LEDGER");
    expect(screen.getByText("$1.20")).toBeInTheDocument();
    expect(screen.getByText("BUY 10 MSFT @ $120.00")).toBeInTheDocument();
    expect(screen.getByText(/Risk limit/)).toBeInTheDocument();
  });
});
