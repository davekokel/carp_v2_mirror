alter table public.cross_instances
add column if not exists tank_pair_id uuid references public.tank_pairs (id);
create index if not exists ix_cross_instances_tank_pair on public.cross_instances (tank_pair_id);

-- optional idempotency guard for same pair/date
do $$
begin
  if not exists (
    select 1 from pg_indexes  where schemaname='public' and indexname='uq_cross_instances_by_pair_date'
  ) then
    execute $I$
      create unique index uq_cross_instances_by_pair_date
      on public.cross_instances(tank_pair_id, cross_date)
      where tank_pair_id is not null
    $I$;
  end if;
end$$;
