DO $$
BEGIN
  alter table public.clutch_instances enable row level security;

  if not exists (select 1 from pg_policy where polrelid='public.clutch_instances'::regclass and polname='app_rw_select_ci_annot')
  then create policy app_rw_select_ci_annot on public.clutch_instances for select to app_rw using (true); end if;

  if not exists (select 1 from pg_policy where polrelid='public.clutch_instances'::regclass and polname='app_rw_update_ci_annot')
  then create policy app_rw_update_ci_annot on public.clutch_instances for update to app_rw using (true) with check (true); end if;
end$$;
