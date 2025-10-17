BEGIN;
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
         pc.father_tank_id,
         cp.planned_name,
         cp.planned_nickname
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
  coalesce(x.cross_name, lp.planned_name, '') as name,
  coalesce(x.cross_nickname, lp.planned_nickname, '') as nickname,
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
