import {
  ArrowRight,
  Beaker,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Database,
  FileCheck2,
  FlaskConical,
  Gauge,
  GitBranch,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  TerminalSquare
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { getOverview, listDatasetCatalog, listDecisions, listExperiments, reproduceExperiment, runResearchExperiment } from "./api";
import CountUp from "./components/CountUp";
import { SkiperThemeToggle } from "./components/SkiperThemeToggle";
import type { DashboardOverview, DatasetCatalogItem, Decision, ExperimentListItem, ReproductionResult } from "./types";

type Status<T> = { data?: T; error?: string; loading: boolean };

const demoFlows = [
  { title: "Trend validation", tag: "Example 01", summary: "Compare a moving-average idea across market regimes before it can enter PAPER mode.", steps: ["Choose a liquid symbol", "Run the reproducible experiment", "Inspect rules and drawdown"] },
  { title: "Research review", tag: "Example 02", summary: "Trace a candidate from a dataset snapshot to an evidence-backed decision record.", steps: ["Open the dataset version", "Review the experiment", "Verify the decision hash"] },
  { title: "Paper session", tag: "Example 03", summary: "Observe a simulated order lifecycle without connecting to a broker or placing real orders.", steps: ["Select an approved strategy", "Start a PAPER session", "Monitor fills and safeguards"] }
];

export function App() {
  const [isDark, setIsDark] = useState(true);
  const [overview, setOverview] = useState<Status<DashboardOverview>>({ loading: true });
  const [experiments, setExperiments] = useState<Status<ExperimentListItem[]>>({ loading: true });
  const [datasets, setDatasets] = useState<Status<DatasetCatalogItem[]>>({ loading: true });
  const [decisions, setDecisions] = useState<Status<Decision[]>>({ loading: true });
  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(null);
  const [selectedExample, setSelectedExample] = useState(0);
  const [reproduction, setReproduction] = useState<Status<ReproductionResult>>({ loading: false });
  const [researchRun, setResearchRun] = useState<Status<{ id: string; status: string }>>({ loading: false });
  const [runSymbol, setRunSymbol] = useState("MSFT");
  const [refreshing, setRefreshing] = useState(false);

  const activeExperiment = useMemo(
    () => experiments.data?.find((item) => item.id === selectedExperiment) ?? experiments.data?.[0],
    [experiments.data, selectedExperiment]
  );

  useEffect(() => { void refreshWorkspace(); }, []);

  async function refreshWorkspace() {
    setRefreshing(true);
    setOverview((current) => ({ ...current, loading: true, error: undefined }));
    setExperiments((current) => ({ ...current, loading: true, error: undefined }));
    setDatasets((current) => ({ ...current, loading: true, error: undefined }));
    setDecisions((current) => ({ ...current, loading: true, error: undefined }));
    const results = await Promise.allSettled([getOverview(), listExperiments(new URLSearchParams({ limit: "8" })), listDatasetCatalog(), listDecisions()]);
    settle(results[0], setOverview);
    settle(results[1], setExperiments, (value) => value.items);
    settle(results[2], setDatasets);
    settle(results[3], setDecisions);
    setRefreshing(false);
  }

  async function runReproduction() {
    if (!activeExperiment) return;
    setReproduction({ loading: true });
    try { setReproduction({ loading: false, data: await reproduceExperiment(activeExperiment.id) }); }
    catch (error) { setReproduction({ loading: false, error: message(error) }); }
  }

  async function startResearchRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setResearchRun({ loading: true });
    try {
      const result = await runResearchExperiment({
        objective: "Test a simple moving-average trend strategy with documented costs and reproducible assumptions.",
        symbol: runSymbol.trim().toUpperCase(),
        start_date: "2023-01-01",
        end_date: "2024-01-01",
        interval: "1d",
        initial_capital: 10_000,
        transaction_cost_bps: 1,
        slippage_bps: 0,
        execution_engine: "python"
      });
      setResearchRun({ loading: false, data: result });
      await refreshWorkspace();
    } catch (error) { setResearchRun({ loading: false, error: message(error) }); }
  }

  return (
    <main className={isDark ? "app app--dark" : "app"}>
      <div className="ambient ambient--one" /><div className="ambient ambient--two" />
      <header className="nav">
        <a className="brand" href="#top" aria-label="Mercury home"><span className="brandMark"><CircleDot size={19} /></span><span>Mercury</span><small>RESEARCH OS</small></a>
        <nav className="navLinks" aria-label="Primary navigation"><a href="#how-it-works">How it works</a><a href="#examples">Examples</a><a href="#workspace">Workspace</a></nav>
        <div className="navActions"><a className="textAction" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API docs <ArrowRight size={14} /></a><SkiperThemeToggle isDark={isDark} onToggle={() => setIsDark((value) => !value)} /></div>
      </header>

      <section className="hero" id="top">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: "easeOut" }}>
          <span className="eyebrow"><span className="liveDot" /> PAPER-ONLY RESEARCH</span>
          <h1>Turn an idea into<br /><em>evidence.</em></h1>
          <p>Mercury is a calm, auditable workspace for testing systematic ideas—then reviewing exactly what happened before a strategy ever reaches PAPER execution.</p>
          <div className="heroActions"><a className="button button--primary" href="#workspace">Open workspace <ArrowRight size={17} /></a><a className="button button--secondary" href="#how-it-works"><Play size={16} /> See how it works</a></div>
        </motion.div>
        <motion.aside className="heroStatus" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, delay: 0.1 }}>
          <div className="statusHeader"><span>LIVE WORKSPACE</span><span className="statusPill">PAPER</span></div>
          <div className="signal"><span className="signalRing" /><span>System safeguards active</span></div>
          <div className="statusRows"><StatusRow label="Research API" value={overview.data ? "Connected" : overview.loading ? "Checking" : "Unavailable"} ok={Boolean(overview.data)} /><StatusRow label="Evidence trail" value="Required" ok /><StatusRow label="Execution mode" value="PAPER only" ok /></div>
          <button className="refreshButton" onClick={() => void refreshWorkspace()} disabled={refreshing}><RefreshCw size={15} className={refreshing ? "spin" : ""} /> {refreshing ? "Refreshing" : "Refresh live data"}</button>
        </motion.aside>
      </section>

      <section className="stats" aria-label="Live workspace summary"><Stat label="Experiments" value={experiments.data?.length ?? 0} loading={experiments.loading} /><Stat label="Dataset versions" value={datasets.data?.reduce((total, item) => total + item.versions.length, 0) ?? 0} loading={datasets.loading} /><Stat label="Recorded decisions" value={decisions.data?.length ?? 0} loading={decisions.loading} /><div className="stat stat--note"><ShieldCheck size={18} /><span>Every result remains reviewable before PAPER execution.</span></div></section>

      <section className="section" id="how-it-works"><div className="sectionHeading"><span className="kicker">THE FLOW</span><h2>How Mercury works</h2><p>No black boxes, no live trading.</p></div><div className="flow"><FlowStep icon={<Database />} number="01" title="Ground the data" text="Use versioned market data with its source, policy, and checksum attached." /><FlowStep icon={<FlaskConical />} number="02" title="Test the idea" text="Run a constrained experiment with declared assumptions and reproducible inputs." /><FlowStep icon={<FileCheck2 />} number="03" title="Review evidence" text="Compare performance, weaknesses, and decision rules—then inspect the audit trail." /><FlowStep icon={<Gauge />} number="04" title="Simulate only" text="Approved strategies may run in PAPER mode. Real-money execution is not available here." /></div></section>

      <section className="section examples" id="examples"><div className="sectionHeading"><span className="kicker">START HERE</span><h2>Learn through examples</h2><p>Pick a path, see the workflow, then open the live workspace.</p></div><div className="exampleLayout"><div className="exampleTabs" role="tablist" aria-label="Example workflows">{demoFlows.map((flow, index) => <button key={flow.title} className={selectedExample === index ? "exampleTab exampleTab--active" : "exampleTab"} onClick={() => setSelectedExample(index)} role="tab" aria-selected={selectedExample === index}><span>{flow.tag}</span><strong>{flow.title}</strong><ChevronRight size={16} /></button>)}</div><motion.article key={selectedExample} className="exampleDetail" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}><span className="exampleTag">{demoFlows[selectedExample].tag}</span><h3>{demoFlows[selectedExample].title}</h3><p>{demoFlows[selectedExample].summary}</p><ol>{demoFlows[selectedExample].steps.map((step) => <li key={step}><CheckCircle2 size={16} /> {step}</li>)}</ol><a className="inlineLink" href="#workspace">Try it in the workspace <ArrowRight size={15} /></a></motion.article></div></section>

      <section className="section workspace" id="workspace"><div className="sectionHeading sectionHeading--row"><div><span className="kicker">YOUR WORKSPACE</span><h2>Use the real research tools</h2><p>Live records appear here when your local database has them.</p></div><span className="paperBadge">PAPER-ONLY</span></div><div className="workspaceGrid">
        <article className="workCard workCard--wide"><div className="workCardHeader"><div><span className="workIcon"><Beaker size={18} /></span><h3>Experiments</h3></div><span>{experiments.data?.length ?? 0} available</span></div>{experiments.loading ? <Loading label="Loading experiments" /> : experiments.error ? <ErrorState error={experiments.error} /> : experiments.data?.length ? <div className="experimentList">{experiments.data.map((experiment) => <button key={experiment.id} className={activeExperiment?.id === experiment.id ? "experiment experiment--active" : "experiment"} onClick={() => { setSelectedExperiment(experiment.id); setReproduction({ loading: false }); }}><span className="experimentSymbol">{experiment.symbol}</span><span><strong>{humanize(experiment.strategy_name)}</strong><small>{experiment.status} · {experiment.start_date} → {experiment.end_date}</small></span><span className="experimentMetric">{metric(experiment.metrics.sharpe_ratio)}<small>Sharpe</small></span></button>)}</div> : <EmptyState icon={<Beaker size={20} />} title="No experiments yet" text="Create or ingest research through the API, then return here to review it." action="Open API docs" />}</article>
        <article className="workCard"><div className="workCardHeader"><div><span className="workIcon"><Play size={18} /></span><h3>Start a research run</h3></div><span>Local only</span></div><p className="cardCopy">Run the Trend validation example against a symbol. It creates an auditable local record—never a live order.</p><form className="runForm" onSubmit={(event) => void startResearchRun(event)}><label htmlFor="run-symbol">Symbol</label><div><input id="run-symbol" value={runSymbol} onChange={(event) => setRunSymbol(event.target.value)} maxLength={12} required /><button className="button button--primary" disabled={researchRun.loading}><Play size={15} /> {researchRun.loading ? "Running…" : "Run example"}</button></div></form>{researchRun.data && <div className="result result--good"><strong>Research run complete</strong><span>Recorded as {researchRun.data.id.slice(0, 8)} · {researchRun.data.status}</span></div>}{researchRun.error && <ErrorState error={researchRun.error} />}</article>
        <article className="workCard"><div className="workCardHeader"><div><span className="workIcon"><RotateCcw size={18} /></span><h3>Verify a run</h3></div></div><p className="cardCopy">Re-run the selected experiment and compare its recorded fingerprints and metrics.</p>{activeExperiment ? <><div className="selectedRun"><span>{activeExperiment.symbol}</span><strong>{humanize(activeExperiment.strategy_name)}</strong><small>{activeExperiment.id}</small></div><button className="button button--primary button--full" onClick={() => void runReproduction()} disabled={reproduction.loading}><RotateCcw size={16} /> {reproduction.loading ? "Verifying run…" : "Reproduce this run"}</button></> : <button className="button button--muted button--full" disabled><RotateCcw size={16} /> Select an experiment first</button>}{reproduction.data && <div className={reproduction.data.match ? "result result--good" : "result result--warn"}><strong>{reproduction.data.match ? "Match verified" : "Review differences"}</strong><span>{reproduction.data.blocking_differences.length ? reproduction.data.blocking_differences.join(", ") : "Recorded metrics and fingerprints agree."}</span></div>}{reproduction.error && <ErrorState error={reproduction.error} />}</article>
        <article className="workCard"><div className="workCardHeader"><div><span className="workIcon"><Database size={18} /></span><h3>Research data</h3></div><span>{datasets.data?.length ?? 0} catalogs</span></div>{datasets.loading ? <Loading label="Loading datasets" /> : datasets.error ? <ErrorState error={datasets.error} /> : datasets.data?.length ? <ul className="compactList">{datasets.data.slice(0, 4).map((dataset) => <li key={dataset.id}><span><strong>{dataset.name}</strong><small>{dataset.versions.length} immutable version{dataset.versions.length === 1 ? "" : "s"}</small></span><GitBranch size={16} /></li>)}</ul> : <EmptyState icon={<Database size={20} />} title="No datasets yet" text="Immutable data snapshots will show up here." />}</article>
        <article className="workCard"><div className="workCardHeader"><div><span className="workIcon"><TerminalSquare size={18} /></span><h3>Decision trail</h3></div><span>{decisions.data?.length ?? 0} records</span></div>{decisions.loading ? <Loading label="Loading decisions" /> : decisions.error ? <ErrorState error={decisions.error} /> : decisions.data?.length ? <ul className="compactList">{decisions.data.slice(0, 4).map((decision) => <li key={decision.id}><span><strong>{humanize(decision.decision_type)}</strong><small>{decision.outcome} · hash {decision.content_hash.slice(0, 8)}</small></span><span className={decision.integrity.verified === false ? "integrity integrity--bad" : "integrity"}>{decision.integrity.verified === false ? "Check" : "Verified"}</span></li>)}</ul> : <EmptyState icon={<TerminalSquare size={20} />} title="No decisions yet" text="When a workflow accepts or rejects a candidate, its evidence appears here." />}</article>
      </div></section>
      <footer><span>Mercury Research OS</span><span>Built for evidence, constrained to PAPER execution.</span><a href="https://reactbits.dev/" target="_blank" rel="noreferrer">React Bits</a><a href="https://skiper-ui.com/v1/skiper4" target="_blank" rel="noreferrer">Skiper UI</a></footer>
    </main>
  );
}

function settle<T, U = T>(result: PromiseSettledResult<T>, set: (value: Status<U>) => void, transform?: (value: T) => U) { if (result.status === "fulfilled") set({ loading: false, data: transform ? transform(result.value) : (result.value as unknown as U) }); else set({ loading: false, error: message(result.reason) }); }
function message(error: unknown) { return error instanceof Error ? error.message : "Could not load this live resource."; }
function humanize(value: string) { return value.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function metric(value: unknown) { return typeof value === "number" ? value.toFixed(2) : "—"; }
function StatusRow({ label, value, ok }: { label: string; value: string; ok: boolean }) { return <div className="statusRow"><span>{label}</span><strong className={ok ? "ok" : "pending"}>{ok && <CheckCircle2 size={14} />}{value}</strong></div>; }
function Stat({ label, value, loading }: { label: string; value: number; loading: boolean }) { return <div className="stat"><span>{label}</span><strong>{loading ? "—" : <CountUp to={value} duration={0.45} separator="," />}</strong></div>; }
function FlowStep({ icon, number, title, text }: { icon: React.ReactNode; number: string; title: string; text: string }) { return <article className="flowStep"><span className="flowNumber">{number}</span><div className="flowIcon">{icon}</div><h3>{title}</h3><p>{text}</p></article>; }
function Loading({ label }: { label: string }) { return <div className="placeholder"><span className="loader" />{label}</div>; }
function ErrorState({ error }: { error: string }) { return <div className="errorState"><strong>Couldn’t load this resource.</strong><span>{error}</span></div>; }
function EmptyState({ icon, title, text, action }: { icon: React.ReactNode; title: string; text: string; action?: string }) { return <div className="emptyState"><span>{icon}</span><strong>{title}</strong><p>{text}</p>{action && <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">{action} <ArrowRight size={14} /></a>}</div>; }
