-- Production reliability: immutable candle revisions, provider circuit-breaker state,
-- and version increments when the canonical OHLCV row changes.
create table if not exists public.market_candle_revisions (
  id bigint generated always as identity primary key,
  instrument_id uuid not null references public.instruments(id) on delete cascade,
  source text not null check (char_length(source) between 1 and 80),
  timeframe_seconds integer not null check (timeframe_seconds > 0),
  candle_at timestamptz not null,
  open numeric(28, 12) not null check (open > 0),
  high numeric(28, 12) not null check (high > 0),
  low numeric(28, 12) not null check (low > 0),
  close numeric(28, 12) not null check (close > 0),
  volume numeric(38, 12) not null default 0 check (volume >= 0),
  content_hash text not null check (content_hash ~ '^[a-f0-9]{64}$'),
  source_revision text not null,
  observed_at timestamptz not null default now(),
  quality_score numeric(5, 4) check (quality_score between 0 and 1),
  constraint market_candle_revisions_identity_hash_key
    unique (instrument_id, source, timeframe_seconds, candle_at, content_hash),
  constraint market_candle_revisions_ohlc_valid check (
    high >= greatest(open, close, low) and low <= least(open, close, high)
  )
);
create index if not exists market_candle_revisions_history_idx
  on public.market_candle_revisions (instrument_id, timeframe_seconds, candle_at desc, observed_at desc);

alter table public.market_candle_revisions enable row level security;
revoke all privileges on table public.market_candle_revisions from anon, authenticated;
grant insert on table public.market_candle_revisions to service_role;
grant usage, select on sequence public.market_candle_revisions_id_seq to service_role;

create table if not exists public.market_data_provider_state (
  provider text primary key check (char_length(provider) between 1 and 80),
  consecutive_failures integer not null default 0 check (consecutive_failures >= 0),
  opened_until timestamptz,
  last_attempt_at timestamptz,
  last_success_at timestamptz,
  last_error_code text,
  updated_at timestamptz not null default now()
);
alter table public.market_data_provider_state enable row level security;
revoke all privileges on table public.market_data_provider_state from anon, authenticated;
grant select, insert, update on table public.market_data_provider_state to service_role;

create or replace function public.bump_market_candle_version()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if row(new.open, new.high, new.low, new.close, new.volume)
     is distinct from row(old.open, old.high, old.low, old.close, old.volume) then
    new.data_version := old.data_version + 1;
  else
    new.data_version := old.data_version;
  end if;
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists market_candles_version_on_change on public.market_candles;
create trigger market_candles_version_on_change
before update on public.market_candles
for each row execute function public.bump_market_candle_version();
