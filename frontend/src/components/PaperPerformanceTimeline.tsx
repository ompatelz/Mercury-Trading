import type { PaperPortfolioHistoryPoint } from "../types";
import "./PaperPerformanceTimeline.css";

export function PaperPerformanceTimeline({ points }: { points: PaperPortfolioHistoryPoint[] }) {
  const values = [...points].sort((a, b) => a.sequence - b.sequence);
  if (!values.length) return <section className="paperTimeline" aria-label="PAPER performance history"><div className="paperTimeline__heading"><span>PERSISTED PORTFOLIO HISTORY</span><strong>No snapshots recorded</strong></div><p>No portfolio snapshots were recorded for this PAPER session, so Mercury cannot draw a performance timeline.</p></section>;
  const equity = values.map((point) => point.equity); const min = Math.min(...equity); const span = Math.max(...equity) - min || 1;
  const path = values.map((point, index) => `${index ? "L" : "M"}${12 + (values.length === 1 ? 148 : index / (values.length - 1) * 296)},${100 - (point.equity - min) / span * 88}`).join(" ");
  const first = values[0]; const last = values[values.length - 1]; const change = last.equity - first.equity;
  return <section className="paperTimeline" aria-label="PAPER performance history"><div className="paperTimeline__heading"><span>PERSISTED PORTFOLIO HISTORY</span><strong>{values.length} snapshot{values.length === 1 ? "" : "s"}</strong></div><svg viewBox="0 0 320 112" role="img" aria-label={`PAPER equity moved from ${money(first.equity)} to ${money(last.equity)}`}><line x1="12" x2="308" y1="100" y2="100" className="paperTimeline__axis" /><path d={path} className="paperTimeline__line" /></svg><div className="paperTimeline__summary"><span><small>FIRST EQUITY</small><strong>{money(first.equity)}</strong></span><span><small>LAST EQUITY</small><strong>{money(last.equity)}</strong></span><span><small>NET CHANGE</small><strong>{`${change >= 0 ? "+" : "-"}$${Math.abs(change).toFixed(2)}`}</strong></span></div><p>Recorded snapshots only · last recorded {stamp(last.timestamp)}</p></section>;
}
function money(value: number) { return `$${value.toFixed(2)}`; }
function stamp(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString(); }
