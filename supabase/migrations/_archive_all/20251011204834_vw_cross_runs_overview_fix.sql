drop view if exists public.vw_cross_runs_overview;

create view public.vw_cross_runs_overview as
select
  ci.id_uuid                as cross_instance_id,
  ci.cross_run_code         as cross_run_code,
  ci.cross_date,
  cr.id_uuid                as cross_id,
  cr.cross_code             as cross_code,
  cr.mother_code            as mom_code,
  cr.father_code            as dad_code,

  -- mother tank label (prefer explicit container id saved on the instance; else derive from live membership)
  coalesce(
    (select coalesce(c.tank_code, c.label) from public.containers c where c.id_uuid = ci.mother_tank_id),
    (select coalesce(c2.tank_code, c2.label)
       from public.fish f2
       join public.fish_tank_memberships m2 on m2.fish_id=f2.id and m2.left_at is null
       join public.containers c2 on c2.id_uuid=m2.container_id and c2.status in ('active','new_tank')
      where f2.fish_code = cr.mother_code
      order by coalesce(c2.activated_at, c2.created_at) desc nulls last
      limit 1)
  ) as mother_tank_label,

  -- father tank label (same fallback)
  coalesce(
    (select coalesce(c.tank_code, c.label) from public.containers c where c.id_uuid = ci.father_tank_id),
    (select coalesce(c2.tank_code, c2.label)
       from public.fish f2
       join public.fish_tank_memberships m2 on m2.fish_id=f2.id and m2.left_at is null
       join public.containers c2 on c2.id_uuid=m2.container_id and c2.status in ('active','new_tank')
      where f2.fish_code = cr.father_code
      order by coalesce(c2.activated_at, c2.created_at) desc nulls last
      limit 1)
  ) as father_tank_label,

  ci.note                   as run_note,
  ci.created_by             as run_created_by,
  ci.created_at             as run_created_at,
  0::int                    as n_clutches,
  0::int                    as n_containers
from public.cross_instances ci
join public.crosses cr
  on cr.id_uuid = ci.cross_id;
