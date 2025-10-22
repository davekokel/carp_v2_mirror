create or replace view public.v_tanks as
select
  t.tank_id,
  coalesce(t.rack, '') || case when t.position is not null then '-'||t.position else '' end as label,
  t.tank_code,
  s.status::text as status,
  s.changed_at as tank_updated_at,
  t.created_at as tank_created_at
from public.tanks t
left join public.v_tanks_current_status s
  on s.tank_id = t.tank_id;
