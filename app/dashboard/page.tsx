import Link from "next/link";
import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { signOut } from "../auth/actions";

export default async function DashboardPage() {
  const supabase = await createSupabaseServerClient();
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) redirect("/auth");

  const [
    { data: memberships, error: membershipsError },
    { data: strategies, error: strategiesError },
    { data: instruments, error: instrumentsError },
  ] = await Promise.all([
    supabase.from("workspace_members").select("workspace_id,role").eq("user_id", user.id),
    supabase.from("strategies").select("id,name,status,created_at").order("created_at", { ascending: false }),
    supabase.from("instruments").select("id,symbol,instrument_type,venue_id,is_active").eq("is_active", true).order("symbol"),
  ]);

  const dataError = membershipsError ?? strategiesError ?? instrumentsError;
  if (dataError) {
    throw new Error(`Unable to load trading desk data: ${dataError.message}`);
  }

  return (
    <main className="container">
      <nav>
        <strong>Multi-Agent Trader</strong>
        <Link href="/strategies">Strategies</Link>
        <Link href="/research">Research Desk</Link>
        <span style={{ marginLeft: "auto" }} className="muted">{user.email}</span>
        <form action={signOut}><button type="submit">Sign out</button></form>
      </nav>
      <section>
        <h1>Trading Desk Foundation</h1>
        <p className="muted">Authenticated · RLS-protected · no execution path enabled.</p>
      </section>
      <section className="grid grid-3">
        <div className="card"><h3>Workspaces</h3><strong>{memberships?.length ?? 0}</strong><p className="muted">Visible memberships</p></div>
        <div className="card"><h3>Strategies</h3><strong>{strategies?.length ?? 0}</strong><p className="muted">Versioned hypotheses</p></div>
        <div className="card"><h3>Instruments</h3><strong>{instruments?.length ?? 0}</strong><p className="muted">Enabled registry entries</p></div>
      </section>
      <section className="card">
        <h2>Canonical instruments</h2>
        <table>
          <thead><tr><th>Symbol</th><th>Type</th><th>Venue ID</th><th>Status</th></tr></thead>
          <tbody>{(instruments ?? []).map((instrument) => (
            <tr key={instrument.id}>
              <td>{instrument.symbol}</td><td>{instrument.instrument_type}</td><td>{instrument.venue_id}</td>
              <td>{instrument.is_active ? "Enabled" : "Disabled"}</td>
            </tr>
          ))}</tbody>
        </table>
      </section>
      <section className="card">
        <h2>Research Desk</h2>
        <p className="muted">Inspect point-in-time run history, condition coverage, insufficient-data reasons and evidence provenance.</p>
        <Link href="/research">Open Research Desk →</Link>
      </section>
      <section className="card">
        <h2>Strategy lifecycle</h2>
        <p className="muted">DRAFT → BACKTESTED → PAPER → APPROVED → LIVE → SUSPENDED → RETIRED</p>
        <Link href="/strategies">Create or version a strategy →</Link>
      </section>
    </main>
  );
}
