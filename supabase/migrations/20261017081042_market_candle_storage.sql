-- Normalized, source-attributed candle storage for crypto and forex.
-- Provider credentials are never stored in this table.
create table if not exists public.market_candles (
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
    fetched_at timestamptz not null default now(),
    source_timestamp timestamptz not null,
    source_revision text,
    quality_score numeric(5, 4) check (quality_score between 0 and 1),
    data_version smallint not null default 1 check (data_version > 0),
    is_closed boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint market_candles_ohlc_valid check (
        high >= greatest(open, close, low)
        and low <= least(open, close, high)
    ),
    constraint market_candles_source_key unique (
        instrument_id, source, timeframe_seconds, candle_at
    )
);

create index if not exists market_candles_lookup_idx
    on public.market_candles (instrument_id, timeframe_seconds, candle_at desc);
create index if not exists market_candles_source_fetched_idx
    on public.market_candles (source, fetched_at desc);

alter table public.market_candles enable row level security;
grant select on public.market_candles to authenticated;
grant select, insert, update, delete on public.market_candles to service_role;
grant usage, select on sequence public.market_candles_id_seq to service_role;

drop policy if exists "authenticated users can read market candles" on public.market_candles;
create policy "authenticated users can read market candles"
    on public.market_candles for select to authenticated using (true);
-- Authenticated and anon roles intentionally receive no write policy.
