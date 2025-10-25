drop view if exists public.v_cross_concepts_overview;

create view public.v_cross_concepts_overview
(
  conceptual_cross_code,
  clutch_code,
  name,
  nickname,
  mom_code,
  dad_code,
  mom_code_tank,
  dad_code_tank,
  n_treatments,
  created_by,
  created_at
)
as
select
  v.clutch_code::text                      as conceptual_cross_code,
  v.clutch_code::text                      as clutch_code,
  coalesce(v.clutch_name,'')::text         as name,
  coalesce(v.clutch_nickname,'')::text     as nickname,
  coalesce(pc.mom_code,'')::text           as mom_code,
  coalesce(pc.dad_code,'')::text           as dad_code,
  coalesce(
    (select c.tank_code from public.containers c where c.id_uuid = pc.mother_tank_id),
    (select c2.tank_code
       from public.fish f2
       join public.fish_tank_memberships m2 on m2.fish_id=f2.id and m2.left_at is null
       join public.containers c2 on c2.id_uuid=m2.container_id and c2.status in ('active','new_tank')
      where f2.fish_code = pc.mom_code
      order by coalesce(c2.activated_at, c2.created_at) desc nulls last
      limit 1),
    ''
  )::text as mom_code_tank,
  coalesce(
    (select c.tank_code from public.containers c where c.id_uuid = pc.father_tank_id),
    (select c2.tank_code
       from public.fish f2
       join public.fish_tank_memberships m2 on m2.fish_id=f2.id and m2.left_at is null
       join public.containers c2 on c2.id_uuid=m2.container_id and c2.status in ('active','new_tank')
      where f2.fish_code = pc.dad_code
      order by coalesce(c2.activated_at, c2.created_at) desc nulls last
      limit 1),
    ''
  )::text as dad_code_tank,
  coalesce(v.n_treatments,0)::int          as n_treatments,
  coalesce(v.created_by,'')::text           as created_by,
  v.created_at::timestamptz                as created_at
from public.v_planned_clutches_overview v
left join public.planned_crosses pc
  on pc.cross_code = v.clutch_code;
