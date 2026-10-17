-- Provision an owner workspace for every new Supabase Auth user and repair existing users.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  new_workspace_id uuid;
begin
  insert into public.workspaces (owner_id, name, slug)
  values (new.id, 'My Workspace', 'workspace-' || replace(new.id::text, '-', ''))
  on conflict (slug) do update set owner_id = excluded.owner_id
  returning id into new_workspace_id;

  insert into public.workspace_members (workspace_id, user_id, role)
  values (new_workspace_id, new.id, 'owner')
  on conflict (workspace_id, user_id) do nothing;

  return new;
end;
$$;

revoke all on function public.handle_new_user() from public;

do $$
begin
  if not exists (
    select 1 from pg_trigger
    where tgname = 'on_auth_user_created'
      and tgrelid = 'auth.users'::regclass
      and not tgisinternal
  ) then
    create trigger on_auth_user_created
      after insert on auth.users
      for each row execute function public.handle_new_user();
  end if;
end;
$$;

do $$
declare
  existing_user record;
  new_workspace_id uuid;
begin
  for existing_user in
    select u.id
    from auth.users u
    where not exists (
      select 1
      from public.workspace_members wm
      where wm.user_id = u.id
    )
  loop
    insert into public.workspaces (owner_id, name, slug)
    values (existing_user.id, 'My Workspace', 'workspace-' || replace(existing_user.id::text, '-', ''))
    on conflict (slug) do update set owner_id = excluded.owner_id
    returning id into new_workspace_id;

    insert into public.workspace_members (workspace_id, user_id, role)
    values (new_workspace_id, existing_user.id, 'owner')
    on conflict (workspace_id, user_id) do nothing;
  end loop;
end;
$$;
