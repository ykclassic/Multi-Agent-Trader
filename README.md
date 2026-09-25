# Multi-Agent Trader

Phase 1 establishes the production foundation for the crypto + forex trading desk.

## Stack
- Next.js App Router on Vercel
- Supabase Auth + PostgreSQL + Row Level Security
- TypeScript
- GitHub Actions CI

## Local setup
1. Copy `.env.example` to `.env.local`.
2. Fill the Supabase URL and publishable key from the Supabase project Connect/API settings.
3. Apply `supabase/migrations/20260925220000_phase1_foundation.sql` with the Supabase CLI or dashboard migration workflow.
4. Install dependencies and run `npm run dev`.

No service-role key belongs in the browser or `.env.example`.

## Phase 1 exit criteria
- Authenticated workspace/domain model with RLS.
- Crypto/forex-only asset, instrument and venue registry.
- Versioned strategy model.
- Initial dashboard.
- Repeatable SQL migration.
- CI validates typecheck, lint and production build.

Live order execution is deliberately disabled in Phase 1.