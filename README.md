# Multi-Agent Trader

AI-powered multi-asset trading desk + research terminal + portfolio/risk operating system.

## Phase 1 — Foundation

This branch establishes the production control-plane foundation defined by the architecture blueprint:

- Next.js App Router / Vercel application shell.
- Supabase Auth with server-side session handling.
- PostgreSQL domain model with RLS.
- Automatic workspace creation at signup.
- Versioned strategy registry and lifecycle.
- Crypto + forex asset, venue and instrument registry.
- Authenticated dashboard.
- CI validation for typecheck, lint and build.

### Local setup

1. Create or connect a Supabase project.
2. Apply the foundation migration in `supabase/migrations`.
3. Copy `.env.example` to `.env.local` and set the Supabase URL and publishable key.
4. Run `npm install` then `npm run dev`.

### Architecture invariant

LLMs reason. Quant systems calculate. Policy systems constrain. Execution systems trade. Databases remember.

Phase 1 intentionally contains no broker credentials, order execution, AI decision authority, or live trading path.

## Scope

Crypto and forex only. Stocks are out of scope.

## Quantitative and market-state engine

The dependency-free Python package under `quant/market_engine` provides:

- Validated OHLCV inputs and deterministic EMA, RSI, ATR, return and annualized realized-volatility features.
- A trend regime plus quality-gated market-state classification (trend, volatility and momentum).
- Candle completeness/freshness checks, with configurable forex session calendars.
- Stop-distance position sizing constrained by per-trade risk and gross notional.
- A pure portfolio risk-policy evaluator for daily loss, peak-to-equity drawdown, gross/net exposure, concentration, open risk, position count and market-data quality/freshness.

Market-state output is blocked when history is insufficient, expected candles are missing, data is stale, or its quality score is below the configured threshold. Risk evaluation fails closed for invalid numeric inputs and unsafe market-data state. Default thresholds are conservative engineering defaults and must be calibrated through historical walk-forward evaluation before being treated as production policy.

Run deterministic tests with Python 3.11+:

```bash
python -m unittest discover -s tests -v
```

CI runs the Python tests alongside the Next.js typecheck, lint and production build. The quant and risk functions are research/policy calculations only. They do not call a broker, create orders, or enable live or paper execution.
