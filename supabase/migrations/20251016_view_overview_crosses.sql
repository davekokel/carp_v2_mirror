BEGIN;

create index if not exists ix_clutch_plans_id on public.clutch_plans(id);
create index if not exists ix_clutch_plans_clutch_code on public.clutch_plans(clutch_code);
create index if not exists ix_planned_crosses_clutch_id on public.planned_crosses(clutch_id);
create index if not exists ix_planned_crosses_cross_id on public.planned_crosses(cross_id);
create index if not exists ix_crosses_id on public.crosses(id);
create index if not exists ix_containers_id on public.containers(id);

create or replace view public.v_overview_crosses as
with latest_planned as (
  select distinct on (cp.id)
         cp.id as clutch_id,
         cp.clutch_code,
         cp.status,
         pc.id as planned_id,
         pc.created_at as planned_created_at,
         pc.cross_id,
         pc.mother_tank_id,
         pc.father_tank_id
  from public.clutch_plans cp
  left join public.planned_crosses pc on pc.clutch_id = cp.id
  order by cp.id, pc.created_at desc nulls last
),
counts as (
  select clutch_id, count(*)::int as planned_count
  from public.planned_crosses
  group by clutch_id
)
select
  cp.clutch_code,
  coalesce(cp.planned_name,'') as name,
  coalesce(cp.planned_nickname,'') as nickname,
  lp.status::text as status,
  coalesce(ct.planned_count,0) as planned_count,
  x.mother_code as mom_code,
  x.father_code as dad_code,
  cm.tank_code as mom_code_tank,
  cf.tank_code as dad_code_tank,
  cp.created_at,
  (cm.tank_code is not null and cf.tank_code is not null) as runnable
from public.clutch_plans cp
left join latest_planned lp on lp.clutch_id = cp.id
left join counts ct on ct.clutch_id = cp.id
left join public.crosses x on x.id = lp.cross_id
left join public.containers cm on cm.id = lp.mother_tank_id
left join public.containers cf on cf.id = lp.father_tank_id;

COMMIT;
