create or replace view public.v_tanks as
with mem as (
  select m.container_id as tank_id, f.fish_code
  from public.fish_tank_memberships m
  join public.fish f on f.id = m.fish_id
),
asg as (
  select a.tank_id, f.fish_code
  from public.fish_tank_assignments a
  join public.fish f on f.id = a.fish_id
  where a.end_at is null
)
select
  t.tank_id,
  coalesce(t.rack,'') || case when t.position is not null then '-'||t.position else '' end as label,
  t.tank_code,
  s.status::text as status,
  s.changed_at as tank_updated_at,
  t.created_at as tank_created_at,
  coalesce(mem.fish_code, asg.fish_code) as fish_code
from public.tanks t
left join public.v_tanks_current_status s on s.tank_id = t.tank_id
left join mem on mem.tank_id = t.tank_id
left join asg on asg.tank_id = t.tank_id;
