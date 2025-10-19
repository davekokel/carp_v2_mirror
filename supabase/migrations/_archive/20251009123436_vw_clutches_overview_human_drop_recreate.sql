begin;
drop view if exists public.vw_clutches_overview_human;
create view public.vw_clutches_overview_human as
with src as (
    select
        c.id_uuid as clutch_id,
        c.date_birth,
        c.created_by,
        c.created_at,
        c.note,
        c.batch_label,
        c.seed_batch_id,
        c.planned_cross_id,
        pc.id_uuid as pc_id,
        cp.clutch_code as cp_clutch_code,
        cp.planned_name as cp_planned_name,
        mt.tank_code as mom_tank_code,
        ft.tank_code as dad_tank_code
    from public.clutches as c
    left join public.planned_crosses as pc on c.planned_cross_id = pc.id_uuid
    left join public.clutch_plans as cp on pc.clutch_id = cp.id_uuid
    left join public.containers as mt on pc.mother_tank_id = mt.id_uuid
    left join public.containers as ft on pc.father_tank_id = ft.id_uuid
)

select
    clutch_id,
    date_birth,
    created_by,
    created_at,
    note,
    batch_label,
    seed_batch_id,
    cp_clutch_code as clutch_code,
    cp_planned_name as clutch_name,
    null::text as clutch_nickname,
    mom_tank_code,
    dad_tank_code
from src;
commit;
