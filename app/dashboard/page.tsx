import { createClient } from "@/lib/supabase/server";

export default async function DashboardPage(){
  const supabase=await createClient();
  const {data:{user}}=await supabase.auth.getUser();
  const {data:workspaces}=user?await supabase.from("workspaces").select("id,name,slug,created_at").order("created_at",{ascending:true}):{data:[]};
  const {data:strategies}=user?await supabase.from("strategies").select("id,name,status,asset_class,updated_at").order("updated_at",{ascending:false}).limit(10):{data:[]};
  return <div className="shell"><aside className="sidebar"><div className="brand">MAT / Desk</div><nav className="nav"><a className="active" href="/dashboard">Overview</a><a href="/dashboard/strategies">Strategies</a><a href="/dashboard/registry">Registry</a></nav></aside>
  <main className="main"><div className="header"><div><div className="eyebrow">Phase 1 · Foundation</div><h1>Workspace dashboard</h1><p className="muted">{user?user.email:"Authentication is not configured yet."}</p></div><span className="badge">Advisory only</span></div>
  <div className="grid"><section className="card"><h3>Workspaces</h3><div className="metric">{workspaces?.length??0}</div><div className="muted">Accessible workspaces</div></section><section className="card"><h3>Strategies</h3><div className="metric">{strategies?.length??0}</div><div className="muted">Visible strategy records</div></section><section className="card"><h3>Asset scope</h3><div className="metric">2</div><div className="muted">Crypto · Forex</div></section><section className="card"><h3>Execution</h3><div className="metric">OFF</div><div className="muted">Live execution is not enabled in Phase 1</div></section></div>
  <section className="card section"><h2>Recent strategies</h2><table className="table"><thead><tr><th>Name</th><th>Asset class</th><th>Status</th></tr></thead><tbody>{(strategies??[]).map(s=><tr key={s.id}><td>{s.name}</td><td>{s.asset_class}</td><td><span className="badge">{s.status}</span></td></tr>)}{(strategies??[]).length===0&&<tr><td colSpan={3} className="muted">No strategies yet.</td></tr>}</tbody></table></section>
  </main></div>;
}