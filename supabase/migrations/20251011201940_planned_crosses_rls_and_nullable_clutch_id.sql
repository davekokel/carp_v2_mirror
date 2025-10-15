-- 1) Fix RLS helper (use pg_policy, not pg_policy)
DO $$
BEGIN
  execute 'alter table public.planned_crosses enable row level security';
  if not exists (select 1 from pg_policy where polrelid=''public.planned_crosses''::regclass and polname=''app_rw_select_planned_crosses'') then
    execute 'create policy app_rw_select_planned_crosses on public.planned_crosses for select to app_rw using (true)';
  end if;
  if not exists (select 1 from pg_policy where polrelid=''public.planned_crosses''::regclass and polname=''app_rw_upsert_planned_crosses'') then
    execute 'create policy app_rw_upsert_planned_crosses on public.planned_crosses for insert, update to app_rw using (true) with check (true)';
  end if;
end
$$ LANGUAGE plpgsql;

-- 2) Relax NOT NULL on clutch_id so insert/upsert can succeed without a pre-linked clutch
DO $$
BEGIN
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='planned_crosses'
      and column_name='clutch_id' and is_nullable='NO'
  ) then
    execute 'alter table public.planned_crosses alter column clutch_id drop not null';
  end if;
end
$$ LANGUAGE plpgsql;
