import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { createStrategy, createStrategyVersion } from "./actions";

export default async function StrategiesPage() {
  const supabase = await createSupabaseServerClient();
  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) redirect("/auth");

  const { data: strategies, error } = await supabase
    .from("strategies")
    .select("id,name,status,strategy_versions(version,created_at)")
    .order("created_at", { ascending: false });
  if (error) throw new Error(`Unable to load strategies: ${error.message}`);

  return (
    <main className="container">
      <nav><strong>Strategies</strong><a href="/dashboard">Dashboard</a></nav>
      <section>
        <h1>Strategy Registry</h1>
        <p className="muted">Declarative, versioned strategy contracts. Foundation mode does not execute orders.</p>
      </section>
      <section className="card">
        <h2>Create strategy</h2>
        <form action={createStrategy} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input name="name" placeholder="e.g. FX Macro Research" required maxLength={120} />
          <select name="asset_class" aria-label="Asset class" required defaultValue="crypto">
            <option value="crypto">Crypto</option>
            <option value="forex">Forex</option>
          </select>
          <button type="submit">Create</button>
        </form>
      </section>
      <section className="grid">
        {(strategies ?? []).map((strategy) => (
          <div className="card" key={strategy.id}>
            <h3>{strategy.name} <span className="pill">{strategy.status}</span></h3>
            <p className="muted">Versions: {(strategy.strategy_versions ?? []).map((version) => version.version).join(", ") || "none"}</p>
            <form action={createStrategyVersion}>
              <input type="hidden" name="strategy_id" value={strategy.id} />
              <button type="submit">Create next version</button>
            </form>
          </div>
        ))}
      </section>
    </main>
  );
}
