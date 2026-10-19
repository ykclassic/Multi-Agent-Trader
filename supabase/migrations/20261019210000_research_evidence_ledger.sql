-- Immutable research evidence ledger for inspectable provenance.
-- Evidence is written only by trusted research services and read through workspace RLS.

alter table public.walk_forward_runs
  add constraint walk_forward_runs_workspace_id_id_key unique (workspace_id, id);

create table if not exists public.research_evidence (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete restrict,
  run_id uuid not null,
  evidence_id text not null check (char_length(trim(evidence_id)) between 1 and 160),
  kind text not null check (kind in ('OBSERVED', 'CALCULATED', 'INFERRED')),
  claim text not null check (char_length(trim(claim)) between 1 and 4000),
  value jsonb not null default '{}'::jsonb,
  source text not null check (char_length(trim(source)) between 1 and 240),
  source_uri text,
  instrument_symbol text not null check (char_length(trim(instrument_symbol)) between 1 and 80),
  occurred_at timestamptz not null,
  published_at timestamptz,
  received_at timestamptz not null,
  freshness_ms bigint check (freshness_ms is null or freshness_ms >= 0),
  quality_score numeric(5,4) check (quality_score is null or quality_score between 0 and 1),
  source_version text not null check (char_length(trim(source_version)) between 1 and 120),
  content_hash text not null check (content_hash ~ '^[a-f0-9]{64}$'),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now(),
  foreign key (workspace_id, run_id)
    references public.walk_forward_runs(workspace_id, id) on delete restrict,
  unique (workspace_id, evidence_id, content_hash),
  check (published_at is null or published_at <= received_at)
);

create index if not exists research_evidence_run_history_idx
  on public.research_evidence (workspace_id, run_id, occurred_at desc);
create index if not exists research_evidence_instrument_time_idx
  on public.research_evidence (instrument_symbol, occurred_at desc);
create index if not exists research_evidence_source_idx
  on public.research_evidence (source, received_at desc);

alter table public.research_evidence enable row level security;
revoke all privileges on table public.research_evidence from public, anon, authenticated, service_role;
grant select on table public.research_evidence to authenticated;
grant select, insert on table public.research_evidence to service_role;

create policy "workspace members can read research evidence"
  on public.research_evidence for select to authenticated
  using ((select private.is_workspace_member(workspace_id)));

-- No UPDATE/DELETE grants or policies: corrections must append a new evidence version.
