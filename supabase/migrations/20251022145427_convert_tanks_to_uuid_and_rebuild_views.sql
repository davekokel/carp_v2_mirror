-- Convert tanks + dependents to UUID and rebuild dependent views
-- Final patched version 2025-10-22

create extension if not exists pgcrypto;

-- 1. drop dependent views that reference tanks.tank_id (bigint)
drop view if exists public.v_tank_occupancy cascade;
drop view if exists public.v_tanks cascade;
drop view if exists public.v_tanks_current_status cascade;

-- 2. add UUID column and update dependents
alter table public.tanks add column if not exists tank_id_uuid uuid default gen_random_uuid();

alter table public.fish_tank_assignments add column if not exists tank_id_uuid uuid;

-- convert bigint tank_id → uuid using the corresponding row in tanks
update public.fish_tank_assignments a
   set tank_id_uuid = t.tank_id_uuid
  from public.tanks t
 where t.tank_id::text = a.tank_id::text;  -- allow bigint→text comparison for mapping

alter table public.fish_tank_assignments drop column tank_id;
alter table public.fish_tank_assignments rename column tank_id_uuid to tank_id;

-- also drop FK from tank_status_history → tanks
alter table public.tank_status_history
  drop constraint if exists tank_status_history_tank_id_fkey;

-- 3. promote UUID to primary key
alter table public.tanks drop constraint if exists tanks_pkey;
alter table public.tanks drop column tank_id;
alter table public.tanks rename column tank_id_uuid to tank_id;
alter table public.tanks add primary key (tank_id);

-- recreate FK from tank_status_history → tanks (UUID world)
alter table public.tank_status_history
  add constraint tank_status_history_tank_id_fkey
  foreign key (tank_id)
  references public.tanks(tank_id)
  on update cascade on delete cascade;

-- 4. recreate v_tanks_current_status (UUID)
create or replace view public.v_tanks_current_status as
select
  t.tank_id,
  s.status,
  s.reason,
  s.changed_at
from public.tanks t
join public.tank_status_history s on s.tank_id = t.tank_id
where s.changed_at = (
  select max(s2.changed_at)
  from public.tank_status_history s2
  where s2.tank_id = s.tank_id
);

-- 5. recreate v_tanks view in UUID world
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