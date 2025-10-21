begin;

create or replace view public.v_clutch_instances_overview as
with pc as (
    select
        p.id as planned_cross_id,
        p.cross_run_code,
        p.mother_fish_code as mom_code,
        p.father_fish_code as dad_code,
        p.mother_tank_code,
        p.father_tank_code,
        p.clutch_code as clutch_code_from_plan,
        p.clutch_name,
        p.clutch_nickname
    from public.planned_crosses AS p
),

ci as (
    select
        c.id as clutch_instance_id,
        c.clutch_code,
        c.birthday,
        c.day_annotated,
        c.annotations_rollup,
        c.planned_cross_id
    from public.clutch_instances AS c
)

select
    ci.clutch_instance_id,
    pc.cross_run_code,
    ci.birthday,
    ci.day_annotated,
    ci.annotations_rollup,
    pc.mom_code,
    pc.dad_code,
    pc.mother_tank_code,
    pc.father_tank_code,
    pc.clutch_name,
    pc.clutch_nickname,
    coalesce(ci.clutch_code, pc.clutch_code_from_plan) as clutch_code
from ci  left join pc AS on ci.planned_cross_id = pc.planned_cross_id;

commit;
