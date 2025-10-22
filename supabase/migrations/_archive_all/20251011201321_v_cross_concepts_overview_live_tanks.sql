create or replace view public.v_cross_concepts_overview as
select
  v.clutch_code::text                      as conceptual_cross_code,
  v.clutch_code::text                      as clutch_code,         -- keep for convenience
  coalesce(v.clutch_name,'')::text         as name,
  coalesce(v.clutch_nickname,'')::text     as nickname,
  coalesce(pc.mom_code,'')::text           as mom_code,
  coalesce(pc.dad_code,'')::text           as dad_code,

  -- Live mom tank: find current active/new_tank container for mom fish_code
  coalesce(momt.tank_code,'')::text        as mom_code_tank,

  -- Live dad tank: find current active/new_tank container for dad fish_code
  coalesce(dadt.tank_code,'')::text        as dad_code_tank,

  coalesce(v.n_treatments,0)::int          as n_treatments,
  coalesce(v.created_by,'')::text          as created_by,
  v.created_at::timestamptz                as created_at
from public.v_planned_clutches_overview v
left join public.planned_crosses pc
  on pc.cross_code = v.clutch_code

-- derive mom tank from live memberships
left join lateral (
  select c.tank_code
  from public.fish f
  join public.fish_tank_memberships m
    on m.fish_id = f.id
   and m.left_at is null
  join public.containers c
    on c.id_uuid = m.container_id
   and c.status in ('active','new_tank')
  where f.fish_code = pc.mom_code
  order by coalesce(c.activated_at, c.created_at) desc nulls last
  limit 1
) momt on true

-- derive dad tank from live memberships
left join lateral (
  select c.tank_code
  from public.fish f
  join public.fish_tank_memberships m
    on m.fish_id = f.id
   and m.left_at is null
  join public.containers c
    on c.id_uuid = m.container_id
   and c.status in ('active','new_tank')
  where f.fish_code = pc.dad_code
  order by coalesce(c.activated_at, c.created_at) desc nulls last
  limit 1
) dadt on true;
