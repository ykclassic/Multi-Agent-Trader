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
