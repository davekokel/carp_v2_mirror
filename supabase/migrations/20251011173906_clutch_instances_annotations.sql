alter table public.clutch_instances
  add column if not exists phenotype text,
  add column if not exists notes text,
  add column if not exists annotated_by text,
  add column if not exists annotated_at timestamptz;

DO $$
BEGIN
  if not exists (select 1 from pg_policy where polrelid='public.clutch_instances'::regclass) then
    execute 'alter table public.clutch_instances enable row level security';
    execute 'create policy app_rw_select_ci on public.clutch_instances for select to app_rw using (true)';
    execute 'create policy app_rw_update_ci on public.clutch_instances for update to app_rw using (true) with check (true)';
  end if;
end
$$ LANGUAGE plpgsql;
