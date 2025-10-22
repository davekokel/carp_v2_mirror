-- Robust refresh helper for mv_fish_search:
-- - First time (not populated): normal REFRESH
-- - Afterwards: CONCURRENTLY

create or replace function public.refresh_mv_fish_search() returns void
language plpgsql
as $fn$
begin
  -- If the MV exists but is not yet populated, do a normal refresh
  if exists (
    select 1
    from pg_class AS c
    join pg_namespace AS n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname = 'mv_fish_search'
      and c.relkind = 'm'
      and not c.relispopulated
  ) then
    execute 'REFRESH MATERIALIZED VIEW public.mv_fish_search';
  else
    -- MV is populated (or will be by now) → use concurrent to avoid write locks
    execute 'REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_fish_search';
  end if;
end;
$fn$;

-- Seed the MV once if it exists and is empty (no-op if already populated)
do $$
begin
  if exists (
    select 1
    from pg_class AS c
    join pg_namespace AS n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname = 'mv_fish_search'
      and c.relkind = 'm'
      and not c.relispopulated
  ) then
    execute 'REFRESH MATERIALIZED VIEW public.mv_fish_search';
  end if;
end$$;
