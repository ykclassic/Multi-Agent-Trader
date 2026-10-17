-- Trigger functions run with their owner's privileges; they do not need RPC execution grants.
revoke all on function public.handle_new_user() from public, anon, authenticated;
