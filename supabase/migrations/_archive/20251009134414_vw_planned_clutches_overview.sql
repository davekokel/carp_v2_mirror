BEGIN;

create or replace view public.vw_planned_clutches_overview as
with x as (
  select
    cp.id_uuid                    as clutch_plan_id,
    pc.id_uuid                    as planned_cross_id,
    cp.clutch_code                as clutch_code,
    cp.planned_name               as clutch_name,
    cp.planned_nickname           as clutch_nickname,
    pc.cross_date                 as cross_date,
    cp.created_by,
    cp.created_at,
    coalesce(cp.note, pc.note)    as note
  from public.clutch_plans cp
  left join public.planned_crosses pc on pc.clutch_id = cp.id_uuid
),
tx as (
  select t.clutch_id as clutch_plan_id, count(*)::int as n_treatments
  from public.clutch_plan_treatments t
  group by 1
)
select
  x.clutch_plan_id,
  x.planned_cross_id,
  x.clutch_code,
  x.clutch_name,
  x.clutch_nickname,
  x.cross_date,
  x.created_by,
  x.created_at,
  x.note,
  coalesce(tx.n_treatments, 0) as n_treatments
from x
left join tx on tx.clutch_plan_id = x.clutch_plan_id
order by coalesce(x.cross_date::timestamp, x.created_at) desc nulls last;

COMMIT;
