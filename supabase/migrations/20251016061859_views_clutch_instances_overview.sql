begin;

create or replace view public.v_clutch_instances_overview as
with pc as (
  select
    p.id                      as planned_cross_id,
    p.cross_run_code          as cross_run_code,
    p.mother_fish_code        as mom_code,
    p.father_fish_code        as dad_code,
    p.mother_tank_code        as mother_tank_code,
    p.father_tank_code        as father_tank_code,
    p.clutch_code             as clutch_code_from_plan,
    p.clutch_name             as clutch_name,
    p.clutch_nickname         as clutch_nickname
  from public.planned_crosses p
),
ci as (
  select
    c.id                      as clutch_instance_id,
    c.clutch_code             as clutch_code,
    c.birthday                as birthday,
    c.day_annotated           as day_annotated,
    c.annotations_rollup      as annotations_rollup,
    c.planned_cross_id        as planned_cross_id
  from public.clutch_instances c
)
select
  ci.clutch_instance_id,
  coalesce(ci.clutch_code, pc.clutch_code_from_plan) as clutch_code,
  pc.cross_run_code,
  ci.birthday,
  ci.day_annotated,
  ci.annotations_rollup,
  pc.mom_code,
  pc.dad_code,
  pc.mother_tank_code,
  pc.father_tank_code,
  pc.clutch_name,
  pc.clutch_nickname
from ci
left join pc on pc.planned_cross_id = ci.planned_cross_id;

commit;
