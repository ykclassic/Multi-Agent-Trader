# System Architecture

## Product
Multi-Agent Trader is an AI-powered multi-asset trading desk, research terminal, and portfolio/risk operating system for crypto and forex.

## Core principle
**LLMs reason. Quant systems calculate. Policy systems constrain. Execution systems trade. Databases remember.**

LLMs never directly place orders and never become the source of truth for prices, positions, balances, sizing, leverage, or risk.

## Canonical flow
```
Market/broker data
  -> Data Fabric
  -> Market State Engine
  -> Analyst Router
  -> parallel specialist analysts
  -> Evidence Resolution
  -> Bull/Bear research
  -> Research Manager
  -> Trader proposal
  -> deterministic Quant Risk Engine
  -> qualitative Risk Debate
  -> Portfolio Manager
  -> deterministic Policy Gate
  -> Execution Planner
  -> Broker/Exchange Adapter
  -> Reconciliation
  -> Portfolio State
  -> Observability/Audit
```

## Planes
### Experience plane
Next.js App Router on Vercel. Dashboard, research terminal, decision trace, strategy configuration, backtests, portfolio and risk views.

### Control plane
Supabase Auth/Postgres/RLS plus workflow APIs. Stores users, strategies, configurations, evidence, decisions, audit records and portfolio state.

### Intelligence plane
Python agent/orchestration service. Specialist analysts, research/debate protocol, trader and PM. All outputs are typed and evidence-linked.

### Quant/risk plane
Python deterministic services for features, indicators, volatility, correlation, sizing, portfolio exposure, limits, slippage estimates and backtest metrics.

### Execution plane
Broker/exchange adapters. Credentials live only in execution services. Orders are idempotent, stateful and reconciled against venue state.

### Data plane
Streaming and historical ingestion with canonical timestamps, provenance, quality scores, freshness TTLs and point-in-time replay.

## Safety boundaries
1. AI output is advisory until it passes deterministic validation.
2. Stale/incomplete market data causes abstention or policy rejection.
3. Numerical risk calculations are never delegated to an LLM.
4. Execution services do not receive arbitrary natural-language instructions.
5. Every decision is reproducible from a versioned market-state snapshot, prompt/model versions, tool outputs and policy configuration.
6. A global kill switch and layered circuit breakers can stop new execution without disabling research.
