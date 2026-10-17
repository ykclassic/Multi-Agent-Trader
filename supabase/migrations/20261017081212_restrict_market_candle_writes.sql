-- Keep shared candle reads available to signed-in users only.
-- Revoke broad default grants explicitly; RLS alone is not a substitute for least privilege.
revoke all privileges on table public.market_candles from anon, authenticated;
grant select on table public.market_candles to authenticated;
grant select, insert, update, delete on table public.market_candles to service_role;
grant usage, select on sequence public.market_candles_id_seq to service_role;
