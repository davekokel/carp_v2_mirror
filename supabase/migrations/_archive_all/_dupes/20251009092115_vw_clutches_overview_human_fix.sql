create or replace view public.v_clutches_overview_human as
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
        c.cross_id,
        pc.cross_code as pc_cross_code,
        pc.mom_code as pc_mom_code,
        pc2.cross_code as pc2_cross_code,
        pc2.mom_code as pc2_mom_code
    from public.clutches as c
    left join public.planned_crosses as pc on c.planned_cross_id = pc.id_uuid
    left join public.crosses as x on c.cross_id = x.id_uuid
    left join public.planned_crosses as pc2 on x.planned_cross_id = pc2.id_uuid
)

select
    clutch_id,
    date_birth,
    created_by,
    created_at,
    note,
    batch_label,
    seed_batch_id,
    null::text as clutch_nickname,
    coalesce(pc_cross_code, pc2_cross_code) as clutch_code,
    coalesce(pc_cross_code, pc2_cross_code) as clutch_name,
    coalesce(pc_mom_code, pc2_mom_code) as mom_code
from src;
