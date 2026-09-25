create extension if not exists pgcrypto;

create type public.asset_class as enum ('crypto','forex');
create type public.workspace_role as enum ('owner','admin','trader','viewer');
create type public.strategy_status as enum ('draft','backtested','paper','approved','live','suspended','retired');

create table public.workspaces(
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null references auth.users(id) on delete cascade,
 name text not null check(char_length(name) between 1 and 120),
 slug text not null unique check(slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
create table public.workspace_members(
 workspace_id uuid not null references public.workspaces(id) on delete cascade,
 user_id uuid not null references auth.users(id) on delete cascade,
 role public.workspace_role not null default 'viewer',
 created_at timestamptz not null default now(),
 primary key(workspace_id,user_id)
);
create table public.assets(
 id uuid primary key default gen_random_uuid(), symbol text not null unique, name text not null,
 asset_class public.asset_class not null, is_active boolean not null default true, created_at timestamptz not null default now()
);
create table public.venues(
 id uuid primary key default gen_random_uuid(), code text not null unique, name text not null,
 asset_class public.asset_class not null, is_active boolean not null default true, created_at timestamptz not null default now()
);
create table public.instruments(
 id uuid primary key default gen_random_uuid(), venue_id uuid not null references public.venues(id),
 asset_id uuid not null references public.assets(id), symbol text not null, base_symbol text not null,
 quote_symbol text not null, instrument_type text not null check(instrument_type in ('spot','perpetual','future','forex_spot')),
 is_active boolean not null default true, created_at timestamptz not null default now(), unique(venue_id,symbol)
);
create table public.strategies(
 id uuid primary key default gen_random_uuid(), workspace_id uuid not null references public.workspaces(id) on delete cascade,
 name text not null check(char_length(name) between 1 and 120), slug text not null,
 asset_class public.asset_class not null, status public.strategy_status not null default 'draft',
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(), unique(workspace_id,slug)
);
create table public.strategy_versions(
 id uuid primary key default gen_random_uuid(), strategy_id uuid not null references public.strategies(id) on delete cascade,
 version integer not null check(version>0), definition jsonb not null, created_at timestamptz not null default now(),
 unique(strategy_id,version)
);

create index workspace_members_user_idx on public.workspace_members(user_id);
create index strategies_workspace_idx on public.strategies(workspace_id);
create index strategy_versions_strategy_idx on public.strategy_versions(strategy_id);
create index instruments_asset_idx on public.instruments(asset_id);

create schema if not exists private;

create or replace function private.is_workspace_member(target_workspace uuid)
returns boolean language sql stable security definer set search_path=''
as $$
 select exists(select 1 from public.workspace_members where workspace_id=target_workspace and user_id=(select auth.uid()));
$$;
create or replace function private.is_workspace_admin(target_workspace uuid)
returns boolean language sql stable security definer set search_path=''
as $$
 select exists(select 1 from public.workspace_members where workspace_id=target_workspace and user_id=(select auth.uid()) and role in ('owner','admin'));
$$;
create or replace function private.can_trade_workspace(target_workspace uuid)
returns boolean language sql stable security definer set search_path=''
as $$
 select exists(select 1 from public.workspace_members where workspace_id=target_workspace and user_id=(select auth.uid()) and role in ('owner','admin','trader'));
$$;

revoke execute on function private.is_workspace_member(uuid) from public, anon;
revoke execute on function private.is_workspace_admin(uuid) from public, anon;
revoke execute on function private.can_trade_workspace(uuid) from public, anon;
grant usage on schema private to authenticated;
grant execute on function private.is_workspace_member(uuid) to authenticated;
grant execute on function private.is_workspace_admin(uuid) to authenticated;
grant execute on function private.can_trade_workspace(uuid) to authenticated;

alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.assets enable row level security;
alter table public.venues enable row level security;
alter table public.instruments enable row level security;
alter table public.strategies enable row level security;
alter table public.strategy_versions enable row level security;

create policy "workspace members can read workspaces" on public.workspaces for select to authenticated using((select private.is_workspace_member(id)) or owner_id=(select auth.uid()));
create policy "authenticated users can create owned workspaces" on public.workspaces for insert to authenticated with check(owner_id=(select auth.uid()));
create policy "owners can update workspaces" on public.workspaces for update to authenticated using(owner_id=(select auth.uid())) with check(owner_id=(select auth.uid()));

create policy "users can read their memberships" on public.workspace_members for select to authenticated using(user_id=(select auth.uid()) or (select private.is_workspace_member(workspace_id)));
create policy "users can add themselves as owner membership" on public.workspace_members for insert to authenticated with check(user_id=(select auth.uid()) and role='owner' and exists(select 1 from public.workspaces w where w.id=workspace_id and w.owner_id=(select auth.uid())));
create policy "workspace admins can manage memberships" on public.workspace_members for update to authenticated using((select private.is_workspace_admin(workspace_id))) with check((select private.is_workspace_member(workspace_id)));
create policy "workspace admins can delete memberships" on public.workspace_members for delete to authenticated using((select private.is_workspace_admin(workspace_id)));

create policy "authenticated users can read registry assets" on public.assets for select to authenticated using(true);
create policy "authenticated users can read registry venues" on public.venues for select to authenticated using(true);
create policy "authenticated users can read registry instruments" on public.instruments for select to authenticated using(true);

create policy "workspace members can read strategies" on public.strategies for select to authenticated using((select private.is_workspace_member(workspace_id)));
create policy "workspace traders can create strategies" on public.strategies for insert to authenticated with check((select private.can_trade_workspace(workspace_id)));
create policy "workspace traders can update strategies" on public.strategies for update to authenticated using((select private.can_trade_workspace(workspace_id))) with check((select private.can_trade_workspace(workspace_id)));
create policy "workspace admins can delete strategies" on public.strategies for delete to authenticated using((select private.is_workspace_admin(workspace_id)));

create policy "workspace members can read strategy versions" on public.strategy_versions for select to authenticated using(exists(select 1 from public.strategies s where s.id=strategy_id and (select private.is_workspace_member(s.workspace_id))));
create policy "workspace traders can create strategy versions" on public.strategy_versions for insert to authenticated with check(exists(select 1 from public.strategies s where s.id=strategy_id and (select private.can_trade_workspace(s.workspace_id))));

create or replace function public.touch_updated_at()
returns trigger language plpgsql set search_path=public as $$ begin new.updated_at=now(); return new; end; $$;
create trigger workspaces_touch_updated_at before update on public.workspaces for each row execute function public.touch_updated_at();
create trigger strategies_touch_updated_at before update on public.strategies for each row execute function public.touch_updated_at();

insert into public.assets(symbol,name,asset_class) values
 ('BTC','Bitcoin','crypto'),('ETH','Ethereum','crypto'),('USD','US Dollar','forex'),('EUR','Euro','forex'),('GBP','British Pound','forex'),('JPY','Japanese Yen','forex')
on conflict(symbol) do nothing;
insert into public.venues(code,name,asset_class) values
 ('BINANCE','Binance','crypto'),('COINBASE','Coinbase','crypto'),('KRAKEN','Kraken','crypto'),('OANDA','OANDA','forex'),('FXCM','FXCM','forex')
on conflict(code) do nothing;
insert into public.instruments(venue_id,asset_id,symbol,base_symbol,quote_symbol,instrument_type)
select v.id,a.id,x.symbol,x.base_symbol,x.quote_symbol,x.instrument_type
from (values
 ('BINANCE','BTC','BTC/USDT','BTC','USDT','spot'),('BINANCE','ETH','ETH/USDT','ETH','USDT','spot'),('COINBASE','BTC','BTC-USD','BTC','USD','spot'),
 ('OANDA','EUR','EUR/USD','EUR','USD','forex_spot'),('OANDA','GBP','GBP/USD','GBP','USD','forex_spot'),('OANDA','JPY','USD/JPY','USD','JPY','forex_spot'),
 ('FXCM','EUR','EUR/USD','EUR','USD','forex_spot'),('FXCM','GBP','GBP/USD','GBP','USD','forex_spot')
) as x(venue_code,asset_symbol,symbol,base_symbol,quote_symbol,instrument_type)
join public.venues v on v.code=x.venue_code join public.assets a on a.symbol=x.asset_symbol
on conflict(venue_id,symbol) do nothing;