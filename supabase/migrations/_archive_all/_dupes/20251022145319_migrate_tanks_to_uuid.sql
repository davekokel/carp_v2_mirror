-- migrate tanks and dependents to UUID ids

create extension if not exists pgcrypto;

-- 1) add a new UUID id column
alter table public.tanks add column if not exists tank_id_uuid uuid default gen_random_uuid();

-- 2) update referencing tables (example shown; repeat for every dependent)
alter table public.fish_tank_assignments add column if not exists tank_id_uuid uuid;
update public.fish_tank_assignments a
  set tank_id_uuid = t.tank_id_uuid
  from public.tanks t
 where a.tank_id = t.tank_id;
alter table public.fish_tank_assignments drop column tank_id;
alter table public.fish_tank_assignments rename column tank_id_uuid to tank_id;

-- 3) replace old bigint tank_id with uuid primary key
alter table public.tanks drop constraint if exists tanks_pkey;
alter table public.tanks drop column tank_id;
alter table public.tanks rename column tank_id_uuid to tank_id;
alter table public.tanks add primary key (tank_id);

-- 4) rebuild v_tanks view for pure uuid world
create or replace view public.v_tanks as
with latest_label as (
  select distinct on (li.tank_id)
         li.tank_id,
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
