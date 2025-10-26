create or replace view public.v_containers as
with live as (
  select
    ftm.tank_uuid,
    count(*)::int as live_count
  from public.fish_tank_memberships ftm
  where ftm.left_at is null
  group by ftm.tank_uuid
)
select
  t.tank_uuid as tank_uuid,
  t.tank_code                      as container_code,
  'tank'::text                     as container_type,
  coalesce(t.status,'')            as status,
  null::int                        as capacity,
  coalesce(live.live_count,0)::int as live_count,
  null::int                        as free_slots,
  t.created_at                     as created_at
from public.tanks t
left join live on live.tank_uuid = t.tank_uuid;

drop view if exists public.v_containers_crossing_candidates cascade;
create view public.v_containers_crossing_candidates as
select *
from public.v_containers
where container_type='tank'
  and coalesce(status,'') in ('active','ready','available','idle')
  and coalesce(live_count,0)=0;
