import type { PaperSessionDashboard } from "../types";
import type { ReactNode } from "react";

export function PaperExecutionLedger({ session }: { session: PaperSessionDashboard }) {
  const { analytics } = session;
  return <section className="paperLedger" aria-label="PAPER execution ledger">
    <div className="paperLedger__heading"><div><span>READ-ONLY EXECUTION LEDGER</span><strong>{session.symbol} · {session.execution_mode}</strong></div><small>{session.status}</small></div>
    <div className="paperLedger__metrics">
      <Metric label="Filled orders" value={`${analytics.filled_order_count} / ${analytics.order_count}`} />
      <Metric label="Fill rate" value={percentage(analytics.fill_rate)} />
      <Metric label="Fees" value={money(analytics.total_fees)} />
      <Metric label="Slippage" value={money(analytics.total_slippage_cost)} />
      <Metric label="Notional" value={money(analytics.total_notional)} />
      <Metric label="Rejected" value={String(analytics.rejected_order_count)} />
    </div>
    <LedgerList title="Recent fills" empty="No fills were recorded for this PAPER session.">
      {session.recent_fills.map((fill) => <li key={fill.id}><span><strong>{fill.side} {number(fill.quantity)} {fill.symbol} @ {money(fill.price)}</strong><small>{timestamp(fill.timestamp)} · fees {money(fill.fees)} · slippage {money(fill.slippage_cost)}</small></span><span className="integrity">PAPER</span></li>)}
    </LedgerList>
    <LedgerList title="Recent orders" empty="No orders were recorded for this PAPER session.">
      {session.recent_orders.map((order) => <li key={order.id}><span><strong>{order.side} {number(order.quantity)} {order.symbol}</strong><small>{timestamp(order.created_at)} · {order.status}{order.rejection_reason ? ` · ${order.rejection_reason}` : ""}</small></span><span className={order.status === "REJECTED" ? "integrity integrity--bad" : "integrity"}>{order.status}</span></li>)}
    </LedgerList>
  </section>;
}

function LedgerList({ title, empty, children }: { title: string; empty: ReactNode; children: ReactNode }) {
  const hasRows = Array.isArray(children) && children.length > 0;
  return <div className="paperLedger__list"><span>{title}</span>{hasRows ? <ul>{children}</ul> : <p>{empty}</p>}</div>;
}
function Metric({ label, value }: { label: string; value: string }) { return <div><span>{label}</span><strong>{value}</strong></div>; }
function money(value: number) { return `$${value.toFixed(2)}`; }
function number(value: number) { return Number.isInteger(value) ? String(value) : value.toFixed(4); }
function percentage(value: number | null) { return value === null ? "—" : `${(value * 100).toFixed(1)}%`; }
function timestamp(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString(); }
