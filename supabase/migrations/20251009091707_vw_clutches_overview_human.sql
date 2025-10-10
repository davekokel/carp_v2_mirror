create or replace view public.vw_clutches_overview_human as
with src as (
  select
    c.id_uuid        as clutch_id,
    c.date_birth,
    c.created_by,
    c.created_at,
    c.note,
    c.batch_label,
    c.seed_batch_id,
    c.planned_cross_id,
    c.cross_id,
    pc.cross_code    as pc_cross_code,
    pc.mom_code      as pc_mom_code,
    cp.clutch_code   as cp_clutch_code,
    cp.planned_name  as cp_planned_name,
    cp.mom_code      as cp_mom_code,
    pc2.cross_code   as pc2_cross_code,
    pc2.mom_code     as pc2_mom_code
  from public.clutches c
  left join public.planned_crosses pc on pc.id_uuid = c.planned_cross_id
  left join public.clutch_plans    cp on cp.planned_cross_id = c.planned_cross_id
  left join public.crosses         x  on x.id_uuid = c.cross_id
  left join public.planned_crosses pc2 on pc2.id_uuid = x.planned_cross_id
)
select
  clutch_id,
  date_birth,
  created_by,
  created_at,
  note,
  batch_label,
  seed_batch_id,
  coalesce(cp_clutch_code, pc_cross_code, pc2_cross_code) as clutch_code,
  coalesce(cp_planned_name, pc_cross_code, pc2_cross_code) as clutch_name,
  null::text                                               as clutch_nickname,
  coalesce(cp_mom_code, pc_mom_code, pc2_mom_code)         as mom_code
from src;
