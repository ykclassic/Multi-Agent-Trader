# Supabase Schema Blueprint

## Core tables
```text
workspaces
workspace_members
strategies
strategy_versions
assets
venues
instruments
market_snapshots
market_observations
market_events
features
evidence
agent_runs
agent_reports
debates
trade_proposals
risk_assessments
policy_decisions
execution_orders
fills
positions
portfolio_snapshots
backtest_runs
backtest_metrics
alerts
audit_logs
prompt_versions
model_versions
```

## Common columns
Use UUID primary keys, created_at/updated_at, workspace_id where user-owned, version fields where immutable, and explicit source/provider timestamps for market data.

## RLS
Every workspace-owned table is protected by workspace membership. Service-role access is restricted to backend services and never exposed to browsers.

## Immutability
Evidence, agent reports, policy decisions and execution events should be append-only or versioned. Avoid destructive updates to decision history.

## Storage
Do not use Postgres as an unbounded raw tick store. Keep large raw market data in a time-series/object storage layer and retain queryable aggregates/canonical snapshots in Postgres.
