begin;
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
    from public.clutch_plans AS cp
    left join public.planned_crosses AS pc on cp.id = pc.clutch_id
    order by cp.id asc, pc.created_at desc nulls last
),

counts as (
    select
        clutch_id,
        count(*)::int as planned_count
    from public.planned_crosses  group by clutch_id
)

select
    cp.clutch_code,
    lp.status::text as status,
    x.mother_code as mom_code,
    x.father_code as dad_code,
    cm.tank_code as mom_code_tank,
    cf.tank_code as dad_code_tank,
    cp.created_at,
    coalesce(x.cross_name, lp.planned_name, '') as name,
    coalesce(x.cross_nickname, lp.planned_nickname, '') as nickname,
    coalesce(ct.planned_count, 0) as planned_count,
    (cm.tank_code is not null and cf.tank_code is not null) as runnable
from public.clutch_plans AS cp
left join latest_planned AS lp on cp.id = lp.clutch_id
left join counts AS ct on cp.id = ct.clutch_id
left join public.crosses AS x on lp.cross_id = x.id
left join public.containers AS cm on lp.mother_tank_id = cm.id
left join public.containers AS cf on lp.father_tank_id = cf.id;
commit;
