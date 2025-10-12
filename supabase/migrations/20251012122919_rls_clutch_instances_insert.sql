do $$
begin
  -- enable RLS (no-op if already enabled)
  alter table public.clutch_instances enable row level security;

  -- allow app to INSERT annotations
  if not exists (
    select 1 from pg_policy
    where polrelid='public.clutch_instances'::regclass
      and polname='app_rw_insert_ci_annot'
  ) then
    create policy app_rw_insert_ci_annot
      on public.clutch_instances
      for insert
      to app_rw
      with check (true);
  end if;

  -- keep select/update permissive, create if they were missing (defensive)
  if not exists (
    select 1 from pg_policy
    where polrelid='public.clutch_instances'::regclass
      and polname='app_rw_select_ci_annot'
  ) then
    create policy app_rw_select_ci_annot
      on public.clutch_instances
      for select
      to app_rw
      using (true);
  end if;

  if not exists (
    select 1 from pg_policy
    where polrelid='public.clutch_instances'::regclass
      and polname='app_rw_update_ci_annot'
  ) then
    create policy app_rw_update_ci_annot
      on public.clutch_instances
      for update
      to app_rw
      using (true) with check (true);
  end if;
end$$;
