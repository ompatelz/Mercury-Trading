import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PaperPerformanceTimeline } from "../src/components/PaperPerformanceTimeline";

afterEach(cleanup);

describe("PaperPerformanceTimeline", () => {
  it("draws equity using persisted snapshots and reports the change", () => {
    render(<PaperPerformanceTimeline points={[{ sequence: 2, timestamp: "2024-01-03T00:00:00Z", cash: 9000, equity: 10150, realized_pnl: 100, unrealized_pnl: 50, exposure: 1150, transaction_costs: 2 }, { sequence: 1, timestamp: "2024-01-02T00:00:00Z", cash: 10000, equity: 10000, realized_pnl: 0, unrealized_pnl: 0, exposure: 0, transaction_costs: 0 }]} />);
    expect(screen.getByRole("region", { name: "PAPER performance history" })).toHaveTextContent("2 snapshots");
    expect(screen.getByRole("img", { name: /10000\.00 to \$10150\.00/ })).toBeInTheDocument();
    expect(screen.getByText("+$150.00")).toBeInTheDocument();
  });
  it("does not invent a chart when no persisted snapshots exist", () => {
    render(<PaperPerformanceTimeline points={[]} />);
    expect(screen.getByText("No snapshots recorded")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
