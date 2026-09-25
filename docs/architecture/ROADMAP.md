# Eight-Phase Implementation Roadmap

## Phase 1 — Foundation
Next.js App Router/Vercel, Supabase Auth/Postgres/RLS, workspace/user/strategy domain, market/instrument registry, dashboard shell, migrations and CI.
**Exit:** authenticated user can create/version a strategy and inspect canonical instruments.

## Phase 2 — Quant Engine
OHLCV ingestion, deterministic features/indicators, volatility/regime calculations, portfolio state, risk engine, freshness/quality scoring.
**Exit:** deterministic market snapshot and risk assessment work without an LLM.

## Phase 3 — AI Research Desk
Technical, macro, news, sentiment; crypto on-chain/derivatives/liquidity/tokenomics; evidence ledger; Bull/Bear debate; evidence resolver.
**Exit:** every research run is typed, traceable and evidence-grounded.

## Phase 4 — Decision Engine
Trader, Risk Debate, Portfolio Manager, Policy Gate, confidence dimensions and circuit breakers.
**Exit:** system produces APPROVE/REJECT/DEFER without live order placement.

## Phase 5 — Backtesting
Point-in-time event replay, realistic execution costs, funding/financing, walk-forward validation, regime segmentation, ablations and calibration.
**Exit:** reproducible leakage-controlled backtest with full lineage.

## Phase 6 — Paper Trading
Real-time feeds, simulated venue, order lifecycle, portfolio accounting, alerts and reconciliation.
**Exit:** continuous paper account operates against realistic execution assumptions.

## Phase 7 — Broker/Exchange Integration
Crypto and forex adapters, credential isolation, idempotent order service and venue reconciliation.
**Exit:** explicitly approved live strategies can place and reconcile orders only behind Policy Gate.

## Phase 8 — Controlled Automation
Research/approval/semi-auto/auto modes, operational dashboards, model/prompt registry, cost/reliability controls, advanced circuit breakers and disaster recovery.
**Exit:** autonomous execution remains bounded by versioned strategy/risk/policy configuration and fully auditable.

## Cross-phase rule
Do not skip foundational validation because later components are technically possible. Live execution depends on validated data, risk, replay, paper trading and reconciliation.
