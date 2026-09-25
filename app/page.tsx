import Link from "next/link";

const modules = [
  ["Research Desk","Evidence-grounded market research and agent workflows."],
  ["Portfolio","Workspace positions, exposure and strategy state."],
  ["Risk","Deterministic limits and portfolio risk controls."],
  ["Strategies","Versioned strategy definitions for crypto and forex."]
];

export default function Home(){
  return <main className="main" style={{margin:"0 auto"}}>
    <div className="header"><div><div className="eyebrow">Foundation</div><h1>Multi-Agent Trader</h1><p className="muted">Crypto + forex trading desk, research terminal and portfolio/risk OS.</p></div><Link className="badge" href="/dashboard">Open dashboard →</Link></div>
    <div className="grid">{modules.map(([title,description])=><section className="card" key={title}><h2>{title}</h2><p className="muted">{description}</p></section>)}</div>
  </main>;
}