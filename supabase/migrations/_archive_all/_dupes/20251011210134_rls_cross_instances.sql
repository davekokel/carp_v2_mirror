DO $$
BEGIN
  alter table public.cross_instances enable row level security;

  if not exists (select 1 from pg_policy where polrelid='public.cross_instances'::regclass and polname='app_rw_select_ci') then
    create policy app_rw_select_ci on public.cross_instances
      for select to app_rw using (true);
  end if;
  if not exists (select 1 from pg_policy where polrelid='public.cross_instances'::regclass and polname='app_rw_insert_ci') then
    create policy app_rw_insert_ci on public.cross_instances
      for insert to app_rw with check (true);
  end if;
  if not exists (select 1 from pg_policy where polrelid='public.cross_instances'::regclass and polname='app_rw_update_ci') then
    create policy app_rw_update_ci on public.cross_instances
      for update to app_rw using (true) with check (true);
  end if;
end
$$ LANGUAGE plpgsql;
