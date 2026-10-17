-- Tighten explicit privileges in projects with permissive default grants.
revoke update, delete, truncate, references, trigger
  on table public.market_candle_revisions from service_role;
grant select, insert on table public.market_candle_revisions to service_role;

revoke delete, truncate, references, trigger
  on table public.market_data_provider_state from service_role;
grant select, insert, update on table public.market_data_provider_state to service_role;
