-- Immutable point-in-time portfolio state and reproducible walk-forward research.
-- Snapshots/results are server-written; authenticated workspace members are read-only.

create table if not exists public.portfolios (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete restrict,
  name text not null check (char_length(trim(name)) between 1 and 120),
  base_currency text not null default 'USD' check (base_currency ~ '^[A-Z]{3,8}$'),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, name),
  unique (id, workspace_id)
);
alter table public.portfolios enable row level security;
revoke all on table public.portfolios from anon;
grant select, insert, update on table public.portfolios to authenticated;
grant select, insert, update on table public.portfolios to service_role;
create policy "workspace members can read portfolios" on public.portfolios
  for select to authenticated using ((select private.is_workspace_member(workspace_id)));
create policy "workspace editors can create portfolios" on public.portfolios
  for insert to authenticated with check ((select private.is_workspace_editor(workspace_id)));
create policy "workspace editors can update portfolios" on public.portfolios
  for update to authenticated using ((select private.is_workspace_editor(workspace_id)))
  with check ((select private.is_workspace_editor(workspace_id)));

create table if not exists public.portfolio_state_snapshots (
  id uuid primary key default gen_random_uuid(),
  portfolio_id uuid not null,
  workspace_id uuid not null,
  as_of timestamptz not null,
  observed_at timestamptz not null default now(),
  source text not null check (source in ('manual_import','historical_replay','read_only_import')),
  base_currency text not null check (base_currency ~ '^[A-Z]{3,8}$'),
  cash_balance numeric(28, 10) not null,
  equity numeric(28, 10) not null check (equity > 0),
  daily_pnl numeric(28, 10) not null,
  peak_equity numeric(28, 10) not null check (peak_equity >= equity),
  gross_notional numeric(28, 10) not null check (gross_notional >= 0),
  net_notional numeric(28, 10) not null,
  open_risk numeric(28, 10) not null check (open_risk >= 0),
  open_positions integer not null check (open_positions >= 0),
  largest_position_notional numeric(28, 10) not null check (largest_position_notional >= 0),
  market_data_quality_score numeric(5, 4) not null check (market_data_quality_score between 0 and 1),
  market_data_as_of timestamptz not null check (market_data_as_of <= as_of),
  positions jsonb not null default '[]'::jsonb check (jsonb_typeof(positions) = 'array'),
  state_hash text not null check (state_hash ~ '^[a-f0-9]{64}$'),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now(),
  foreign key (portfolio_id, workspace_id) references public.portfolios(id, workspace_id) on delete restrict,
  unique (portfolio_id, as_of, source, state_hash)
);
create index if not exists portfolio_state_history_idx
  on public.portfolio_state_snapshots (portfolio_id, as_of desc, observed_at desc);
create index if not exists portfolio_state_workspace_idx
  on public.portfolio_state_snapshots (workspace_id, as_of desc);
alter table public.portfolio_state_snapshots enable row level security;
revoke all privileges on table public.portfolio_state_snapshots from anon, authenticated;
grant select on table public.portfolio_state_snapshots to authenticated;
revoke update, delete, truncate, references, trigger on table public.portfolio_state_snapshots from service_role;
grant select, insert on table public.portfolio_state_snapshots to service_role;
create policy "workspace members can read portfolio state snapshots"
  on public.portfolio_state_snapshots for select to authenticated
  using ((select private.is_workspace_member(workspace_id)));

create table if not exists public.walk_forward_runs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete restrict,
  created_by uuid references auth.users(id) on delete set null,
  asset_class text not null check (asset_class in ('crypto','forex')),
  instrument_id uuid references public.instruments(id) on delete set null,
  instrument_symbol text not null check (char_length(trim(instrument_symbol)) between 1 and 80),
  timeframe_seconds integer not null check (timeframe_seconds > 0),
  data_start_at timestamptz not null,
  data_end_at timestamptz not null check (data_end_at > data_start_at),
  algorithm_version text not null check (char_length(algorithm_version) between 1 and 100),
  strategy_id text not null check (char_length(strategy_id) between 1 and 100),
  run_hash text not null check (run_hash ~ '^[a-f0-9]{64}$'),
  status text not null check (status in ('completed','insufficient_data','failed')),
  config jsonb not null check (jsonb_typeof(config) = 'object'),
  summary jsonb not null check (jsonb_typeof(summary) = 'object'),
  folds jsonb not null default '[]'::jsonb check (jsonb_typeof(folds) = 'array'),
  condition_metrics jsonb not null default '{}'::jsonb check (jsonb_typeof(condition_metrics) = 'object'),
  created_at timestamptz not null default now(),
  unique (workspace_id, run_hash)
);
create index if not exists walk_forward_workspace_history_idx
  on public.walk_forward_runs (workspace_id, created_at desc);
create index if not exists walk_forward_instrument_history_idx
  on public.walk_forward_runs (instrument_symbol, timeframe_seconds, data_start_at, data_end_at);
alter table public.walk_forward_runs enable row level security;
revoke all privileges on table public.walk_forward_runs from anon, authenticated;
grant select on table public.walk_forward_runs to authenticated;
revoke update, delete, truncate, references, trigger on table public.walk_forward_runs from service_role;
grant select, insert on table public.walk_forward_runs to service_role;
create policy "workspace members can read walk-forward runs"
  on public.walk_forward_runs for select to authenticated
  using ((select private.is_workspace_member(workspace_id)));

-- Select the latest revision observed no later than each candle's close plus a
-- bounded ingestion allowance. Later corrections are deliberately excluded.
create or replace function public.get_point_in_time_market_candles(
  p_instrument_id uuid,
  p_timeframe_seconds integer,
  p_start_at timestamptz,
  p_end_at timestamptz,
  p_max_observation_delay_seconds integer default 300
)
returns table (
  candle_at timestamptz,
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  volume numeric,
  observed_at timestamptz,
  content_hash text,
  quality_score numeric
)
language sql
stable
security invoker
set search_path = ''
as $$
  select distinct on (r.candle_at)
    r.candle_at, r.open, r.high, r.low, r.close, r.volume,
    r.observed_at, r.content_hash, r.quality_score
  from public.market_candle_revisions r
  where r.instrument_id = p_instrument_id
    and r.timeframe_seconds = p_timeframe_seconds
    and r.candle_at >= p_start_at
    and r.candle_at < p_end_at
    and p_timeframe_seconds > 0
    and p_max_observation_delay_seconds between 0 and 86400
    and r.observed_at <= r.candle_at
      + ((p_timeframe_seconds + p_max_observation_delay_seconds) * interval '1 second')
  order by r.candle_at, r.observed_at desc, r.id desc;
$$;
revoke all on function public.get_point_in_time_market_candles(uuid, integer, timestamptz, timestamptz, integer) from public, anon, authenticated;
grant execute on function public.get_point_in_time_market_candles(uuid, integer, timestamptz, timestamptz, integer) to service_role;


create table if not exists public.risk_calibration_runs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete restrict,
  portfolio_id uuid references public.portfolios(id) on delete restrict,
  calibration_version text not null check (char_length(calibration_version) between 1 and 100),
  run_hash text not null check (run_hash ~ '^[a-f0-9]{64}$'),
  snapshot_count integer not null check (snapshot_count >= 0),
  sample_count integer not null check (sample_count >= 0),
  data_start_at timestamptz,
  data_end_at timestamptz,
  min_samples_required integer not null check (min_samples_required > 0),
  status text not null check (status in ('completed','insufficient_data')),
  candidate_results jsonb not null check (jsonb_typeof(candidate_results) = 'array'),
  coverage_gaps jsonb not null default '[]'::jsonb check (jsonb_typeof(coverage_gaps) = 'array'),
  created_at timestamptz not null default now(),
  unique (workspace_id, run_hash),
  check (data_start_at is null or data_end_at is null or data_end_at >= data_start_at)
);
create index if not exists risk_calibration_workspace_history_idx
  on public.risk_calibration_runs (workspace_id, created_at desc);
alter table public.risk_calibration_runs enable row level security;
revoke all privileges on table public.risk_calibration_runs from anon, authenticated;
grant select on table public.risk_calibration_runs to authenticated;
revoke update, delete, truncate, references, trigger on table public.risk_calibration_runs from service_role;
grant select, insert on table public.risk_calibration_runs to service_role;
create policy "workspace members can read risk calibration runs"
  on public.risk_calibration_runs for select to authenticated
  using ((select private.is_workspace_member(workspace_id)));
