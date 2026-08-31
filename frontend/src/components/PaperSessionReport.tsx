import type { PaperPortfolioHistoryPoint, PaperSessionDashboard } from "../types";

type PaperSessionReportProps = { session: PaperSessionDashboard; history: PaperPortfolioHistoryPoint[] };

export function PaperSessionReport({ session, history }: PaperSessionReportProps) {
  function download() {
    const blob = new Blob([buildPaperSessionReport(session, history)], { type: "text/markdown;charset=utf-8" });
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = `mercury-paper-session-${safeFilename(session.id)}.md`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(href);
  }

  return <section className="paperReport" aria-label="PAPER session report export"><div><span>READ-ONLY EVIDENCE REPORT</span><p>Download the persisted session record as Markdown. This export cannot place, modify, or replay an order.</p></div><button type="button" className="paperReport__button" onClick={download}>Download Markdown</button></section>;
}

export function buildPaperSessionReport(session: PaperSessionDashboard, history: PaperPortfolioHistoryPoint[]) {
  const snapshots = [...history].sort((left, right) => left.sequence - right.sequence);
  const summary = snapshots.length ? `Persisted portfolio snapshots: ${snapshots.length} (${snapshotStamp(snapshots[0])} to ${snapshotStamp(snapshots[snapshots.length - 1])}).` : "Persisted portfolio snapshots: none recorded.";
  return [
    "# Mercury PAPER Session Evidence Report", "",
    "> PAPER-only and read-only. This document reflects persisted records only; it cannot create, modify, replay, or transmit an order.", "",
    "## Session", `- Session ID: ${session.id}`, `- Strategy: ${session.strategy_name}`, `- Symbol: ${session.symbol}`, `- Interval: ${session.interval}`, `- Execution mode: ${session.execution_mode}`, `- Status: ${session.status}`, `- Cash: ${money(session.cash)}`, `- Equity: ${money(session.equity)}`, `- PnL: ${money(session.pnl)}`, "",
    "## Persisted execution analytics", `- Orders: ${session.analytics.order_count}`, `- Filled orders: ${session.analytics.filled_order_count}`, `- Rejected orders: ${session.analytics.rejected_order_count}`, `- Fills: ${session.analytics.fill_count}`, `- Fill rate: ${percentage(session.analytics.fill_rate)}`, `- Total notional: ${money(session.analytics.total_notional)}`, `- Total fees: ${money(session.analytics.total_fees)}`, `- Total slippage cost: ${money(session.analytics.total_slippage_cost)}`, "",
    "## Recent persisted fills", ...rows(session.recent_fills.map((fill) => `- ${stamp(fill.timestamp)} | ${fill.side} ${quantity(fill.quantity)} ${fill.symbol} @ ${money(fill.price)} | fees ${money(fill.fees)} | slippage ${money(fill.slippage_cost)}`), "No persisted fills were recorded."), "",
    "## Recent persisted orders", ...rows(session.recent_orders.map((order) => `- ${stamp(order.created_at)} | ${order.status} | ${order.side} ${quantity(order.quantity)} ${order.symbol}${order.rejection_reason ? ` | reason: ${order.rejection_reason}` : ""}`), "No persisted orders were recorded."), "",
    "## Performance history", summary, ...rows(snapshots.map((point) => `- #${point.sequence} | ${stamp(point.timestamp)} | equity ${money(point.equity)} | cash ${money(point.cash)} | realized PnL ${money(point.realized_pnl)} | unrealized PnL ${money(point.unrealized_pnl)} | exposure ${money(point.exposure)} | costs ${money(point.transaction_costs)}`), "No performance timeline is shown because no persisted portfolio snapshots were recorded."), ""
  ].join("\n");
}

function rows(values: string[], empty: string) { return values.length ? values : [`- ${empty}`]; }
function money(value: number | null | undefined) { return typeof value === "number" ? `$${value.toFixed(2)}` : "not recorded"; }
function percentage(value: number | null) { return value === null ? "not recorded" : `${(value * 100).toFixed(1)}%`; }
function quantity(value: number) { return Number.isInteger(value) ? String(value) : value.toFixed(4); }
function stamp(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toISOString(); }
function snapshotStamp(point: PaperPortfolioHistoryPoint) { return stamp(point.timestamp); }
function safeFilename(value: string) { return value.replace(/[^a-z0-9_-]+/gi, "-").replace(/^-+|-+$/g, "") || "session"; }
