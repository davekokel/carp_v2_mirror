create or replace view public.v_tanks as
with latest_label as (
  select distinct on (li.tank_id)
         li.tank_id::bigint as tank_id,     -- cast uuid → bigint to match public.tanks.tank_id
         li.fish_code
  from public.label_items li
  where li.fish_code is not null and li.fish_code <> ''
  order by li.tank_id, li.rendered_at desc nulls last, li.updated_at desc nulls last
)
select
  t.tank_id,
  coalesce(t.rack,'') || case when t.position is not null then '-'||t.position else '' end as label,
  t.tank_code,
  case
    when s.status::text in ('occupied','stocked') then 'active'
    when s.status::text in ('incoming')          then 'new_tank'
    else s.status::text
  end as status,
  s.changed_at  as tank_updated_at,
  t.created_at  as tank_created_at,
  coalesce(f.fish_code, ll.fish_code) as fish_code
from public.tanks t
left join public.v_tanks_current_status s on s.tank_id = t.tank_id
left join public.fish_tank_assignments a  on a.tank_id = t.tank_id and a.end_at is null
left join public.fish f                   on f.id = a.fish_id
left join latest_label ll                 on ll.tank_id = t.tank_id;
