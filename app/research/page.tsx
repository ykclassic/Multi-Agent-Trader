import Link from "next/link";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { signOut } from "../auth/actions";

type ResearchRun = {
  id: string;
  instrument_symbol: string;
  asset_class: string;
  timeframe_seconds: number;
  data_start_at: string;
  data_end_at: string;
  algorithm_version: string;
  strategy_id: string;
  status: "completed" | "insufficient_data" | "failed";
  run_hash: string;
  config: Record<string, unknown>;
  summary: Record<string, unknown>;
  folds: unknown[];
  condition_metrics: Record<string, unknown>;
  created_at: string;
};

type ResearchEvidence = {
  id: string;
  run_id: string;
  evidence_id: string;
  kind: "OBSERVED" | "CALCULATED" | "INFERRED";
  claim: string;
  value: unknown;
  source: string;
  source_uri: string | null;
  instrument_symbol: string;
  occurred_at: string;
  published_at: string | null;
  received_at: string;
  freshness_ms: number | null;
  quality_score: number | null;
  source_version: string;
  content_hash: string;
};

function stamp(value: string | null | undefined) {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toISOString().replace("T", " ").replace(".000Z", " UTC").replace("Z", " UTC");
}

function safeSourceUrl(value: string | null) {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function pretty(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function gaps(run: ResearchRun) {
  const summaryGaps = run.summary?.coverage_gaps;
  if (Array.isArray(summaryGaps)) return summaryGaps.map(String);
  if (run.status === "insufficient_data") return ["The run did not store structured coverage_gaps; inspect the run configuration and logs."];
  if (run.status === "failed") return ["The run failed; inspect its run record and workflow logs."];
  return [];
}

export default async function ResearchPage() {
  const supabase = await createSupabaseServerClient();
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) redirect("/auth");

  const [{ data: rawRuns, error: runsError }, { data: rawEvidence, error: evidenceError }] = await Promise.all([
    supabase.from("walk_forward_runs")
      .select("id,instrument_symbol,asset_class,timeframe_seconds,data_start_at,data_end_at,algorithm_version,strategy_id,status,run_hash,config,summary,folds,condition_metrics,created_at")
      .order("created_at", { ascending: false }).limit(100),
    supabase.from("research_evidence")
      .select("id,run_id,evidence_id,kind,claim,value,source,source_uri,instrument_symbol,occurred_at,published_at,received_at,freshness_ms,quality_score,source_version,content_hash")
      .order("received_at", { ascending: false }).limit(200),
  ]);

  const runs = (rawRuns ?? []) as ResearchRun[];
  const evidence = (rawEvidence ?? []) as ResearchEvidence[];
  const insufficient = runs.filter((run) => run.status === "insufficient_data").length;
  const completed = runs.filter((run) => run.status === "completed").length;

  return (
    <main className="container">
      <nav style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <strong>Research Desk</strong>
        <Link href="/dashboard">Dashboard</Link>
        <Link href="/strategies">Strategies</Link>
        <span className="muted" style={{ marginLeft: "auto" }}>{user.email}</span>
        <form action={signOut}><button type="submit">Sign out</button></form>
      </nav>

      <section>
        <h1>Research Run History</h1>
        <p className="muted">Read-only, point-in-time quantitative research. Results are evidence, not trade instructions. Live and paper execution are disabled.</p>
      </section>

      <section className="grid grid-3">
        <div className="card"><h3>Runs loaded</h3><strong>{runs.length}</strong><p className="muted">Most recent 100 visible under workspace RLS</p></div>
        <div className="card"><h3>Completed</h3><strong>{completed}</strong><p className="muted">Completed evaluations only</p></div>
        <div className="card"><h3>Insufficient data</h3><strong>{insufficient}</strong><p className="muted">Not a successful evaluation; coverage gaps shown below</p></div>
      </section>

      {runsError ? <section className="card"><h2>Research history unavailable</h2><p role="alert">{runsError.message}</p></section> : null}

      <section className="card">
        <h2>Research runs</h2>
        {runs.length === 0 && !runsError ? <p className="muted">No research runs are visible yet. Run the trusted point-in-time research workflow to create a traceable report.</p> : null}
        {runs.map((run) => {
          const coverageGaps = gaps(run);
          const counts = run.summary?.condition_counts ?? run.summary?.condition_coverage ?? {};
          return (
            <article key={run.id} id={run.id} style={{ borderTop: "1px solid var(--border, #ddd)", paddingTop: 16, marginTop: 16 }}>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>{run.instrument_symbol} · {run.timeframe_seconds}s</h3>
                <span className="pill">{run.status}</span>
                <span className="muted">{stamp(run.created_at)}</span>
              </div>
              <p className="muted">Data window: {stamp(run.data_start_at)} → {stamp(run.data_end_at)}</p>
              <p><strong>Run ID:</strong> <code>{run.id}</code></p>
              <p><strong>Run hash:</strong> <code>{run.run_hash}</code></p>
              <p><strong>Strategy / algorithm:</strong> {run.strategy_id} / {run.algorithm_version}</p>
              <div className="grid grid-3">
                <div><strong>Folds</strong><p>{run.folds?.length ?? 0}</p></div>
                <div><strong>Observations</strong><p>{String(run.summary?.observations ?? "Not recorded")}</p></div>
                <div><strong>Condition coverage</strong><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{pretty(run.condition_metrics && Object.keys(run.condition_metrics).length ? run.condition_metrics : counts)}</pre></div>
              </div>
              {coverageGaps.length > 0 ? <div role="status"><h4>Why this run is insufficient</h4><ul>{coverageGaps.map((gap) => <li key={gap}>{gap.replaceAll("_", " ")}</li>)}</ul></div> : null}
              <details><summary>Configuration and full summary</summary><h4>Configuration</h4><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{pretty(run.config)}</pre><h4>Summary</h4><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{pretty(run.summary)}</pre></details>
            </article>
          );
        })}
      </section>

      <section className="card">
        <h2>Evidence ledger and source provenance</h2>
        <p className="muted">Each record shows its claim type, source, source version, event/publication/receipt times, freshness, quality and immutable content hash.</p>
        {evidenceError ? <div role="status"><p><strong>Evidence ledger is not available from the database yet.</strong></p><p className="muted">{evidenceError.message}. The evidence-ledger migration must be applied before this section can display records.</p></div> : null}
        {!evidenceError && evidence.length === 0 ? <p className="muted">No evidence records are persisted yet. This is an honest empty state, not evidence that agents or debates ran.</p> : null}
        {evidence.map((item) => (
          <article key={item.id} style={{ borderTop: "1px solid var(--border, #ddd)", paddingTop: 16, marginTop: 16 }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <strong>{item.evidence_id}</strong><span className="pill">{item.kind}</span><span>{item.instrument_symbol}</span>
              <Link href={`/research#${item.run_id}`}>Associated run</Link>
            </div>
            <p>{item.claim}</p>
            <p><strong>Source:</strong> {item.source} {item.source_version}</p>
            {safeSourceUrl(item.source_uri) ? <p><a href={safeSourceUrl(item.source_uri)!} target="_blank" rel="noreferrer">Open source</a></p> : null}
            <p className="muted">Occurred: {stamp(item.occurred_at)} · Published: {stamp(item.published_at)} · Received: {stamp(item.received_at)}</p>
            <p className="muted">Freshness: {item.freshness_ms === null ? "Not recorded" : `${item.freshness_ms} ms`} · Quality: {item.quality_score === null ? "Not recorded" : item.quality_score}</p>
            <details><summary>Value and integrity</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{pretty(item.value)}</pre><p>Content hash: <code>{item.content_hash}</code></p></details>
          </article>
        ))}
      </section>
    </main>
  );
}
