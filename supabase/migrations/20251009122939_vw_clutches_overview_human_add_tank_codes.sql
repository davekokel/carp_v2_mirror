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
    pc.id_uuid       as pc_id,
    cp.clutch_code   as cp_clutch_code,
    cp.planned_name  as cp_planned_name,
    mt.tank_code     as mom_tank_code,
    ft.tank_code     as dad_tank_code
  from public.clutches c
  left join public.planned_crosses pc on pc.id_uuid = c.planned_cross_id
  left join public.clutch_plans    cp on cp.id_uuid = pc.clutch_id
  left join public.containers      mt on mt.id_uuid = pc.mother_tank_id
  left join public.containers      ft on ft.id_uuid = pc.father_tank_id
)
select
  clutch_id,
  date_birth,
  created_by,
  created_at,
  note,
  batch_label,
  seed_batch_id,
  cp_clutch_code      as clutch_code,
  cp_planned_name     as clutch_name,
  null::text          as clutch_nickname,
  mom_tank_code,
  dad_tank_code
from src;
