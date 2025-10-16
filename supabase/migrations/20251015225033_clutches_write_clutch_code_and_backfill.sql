-- add clutch_code if not present
alter table public.clutches
  add column if not exists clutch_code text;

-- backfill clutch_code from planned_crosses → clutch_plans (best available)
update public.clutches cl
set clutch_code = cp.clutch_code
from public.cross_instances ci
join public.crosses x            on x.id = ci.cross_id
left join public.planned_crosses pc on pc.cross_id = x.id
left join public.clutch_plans   cp on cp.id = pc.clutch_id
where cl.cross_instance_id = ci.id
  and cl.clutch_code is null
  and cp.clutch_code is not null;

-- optional: lineage guard (each run linked to only one concept by code)
create unique index if not exists uq_clutches_run_code
  on public.clutches (cross_instance_id, coalesce(clutch_code,''));
