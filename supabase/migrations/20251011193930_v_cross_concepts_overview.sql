create or replace view public.v_cross_concepts_overview as
select
  v.clutch_code::text                    as clutch_code,
  coalesce(v.clutch_name,'')::text       as name,
  coalesce(v.clutch_nickname,'')::text   as nickname,
  coalesce(pc.mom_code,'')::text         as mom_code,
  coalesce(pc.dad_code,'')::text         as dad_code,
  coalesce(cm.tank_code,'')::text        as mom_code_tank,
  coalesce(cd.tank_code,'')::text        as dad_code_tank,
  coalesce(v.n_treatments,0)::int        as n_treatments,
  coalesce(v.created_by,'')::text        as created_by,
  v.created_at::timestamptz              as created_at
from public.vw_planned_clutches_overview v
left join public.planned_crosses pc
  on pc.cross_code = v.clutch_code
left join public.containers cm
  on cm.id_uuid = pc.mother_tank_id
left join public.containers cd
  on cd.id_uuid = pc.father_tank_id;
