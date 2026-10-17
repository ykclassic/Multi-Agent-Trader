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
2. Apply `supabase/migrations/20260925210000_foundation.sql`.
3. Copy `.env.example` to `.env.local` and set the Supabase URL and publishable key.
4. Run `npm install` then `npm run dev`.

### Architecture invariant

LLMs reason. Quant systems calculate. Policy systems constrain. Execution systems trade. Databases remember.

Phase 1 intentionally contains no broker credentials, order execution, AI decision authority, or live trading path.

## Scope

Crypto and forex only. Stocks are out of scope.


## Phase 2 — Deterministic quant engine (initial vertical slice)

A dependency-free Python package under `quant/market_engine` provides validated OHLCV inputs, deterministic EMA/RSI/ATR/realized-volatility features, a simple trend regime label, and stop-distance-based position sizing with risk and notional caps. It rejects malformed, unordered, future-dated, and stale candle data. These functions have no network, database, broker, or LLM dependencies.

Run the unit tests with `python -m unittest discover -s tests -v` (Python 3.11+). CI runs these tests alongside the Next.js typecheck, lint, and production build.

This is the first Phase 2 slice, not yet a complete market-data pipeline: exchange/forex feed adapters, candle persistence, gap detection, point-in-time portfolio state, and full risk policy evaluation remain follow-on work. All outputs are research/risk calculations only; order execution remains disabled.
