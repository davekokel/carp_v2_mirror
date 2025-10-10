BEGIN;

drop view if exists public.vw_clutches_overview_human;

create view public.vw_clutches_overview_human as
with base as (
  select
    c.id_uuid        as clutch_id,
    c.date_birth,
    c.created_by,
    c.created_at,
    c.note,
    c.batch_label,
    c.seed_batch_id,
    c.planned_cross_id,
    cp.clutch_code   as clutch_code,
    cp.planned_name  as clutch_name,
    coalesce(mt.label, mt.tank_code) as mom_tank_label,
    coalesce(ft.label, ft.tank_code) as dad_tank_label
  from public.clutches c
  left join public.planned_crosses pc on pc.id_uuid = c.planned_cross_id
  left join public.clutch_plans    cp on cp.id_uuid = pc.clutch_id
  left join public.containers      mt on mt.id_uuid = pc.mother_tank_id
  left join public.containers      ft on ft.id_uuid = pc.father_tank_id
),
instances as (
  select cc.clutch_id, count(*)::int as n_instances
  from public.clutch_containers cc
  group by cc.clutch_id
),
crosses_direct as (
  -- if crosses carries clutch_id
  select x.clutch_id, count(*)::int as n_crosses
  from public.crosses x
  where x.clutch_id is not null
  group by x.clutch_id
),
crosses_via_clutches as (
  -- otherwise: clutches.cross_id → crosses.id_uuid (1:1); count it as 1
  select c.id_uuid as clutch_id, count(x.id_uuid)::int as n_crosses
  from public.clutches c
  left join public.crosses x on x.id_uuid = c.cross_id
  group by c.id_uuid
),
crosses_union as (
  select clutch_id, sum(n_crosses)::int as n_crosses
  from (
    select * from crosses_direct
    union all
    select * from crosses_via_clutches
  ) u
  group by clutch_id
)
select
  b.clutch_id,
  b.date_birth,
  b.created_by,
  b.created_at,
  b.note,
  b.batch_label,
  b.seed_batch_id,
  b.clutch_code,
  b.clutch_name,
  null::text as clutch_nickname,
  b.mom_tank_label,
  b.dad_tank_label,
  coalesce(i.n_instances, 0) as n_instances,
  coalesce(x.n_crosses, 0)   as n_crosses
from base b
left join instances     i on i.clutch_id = b.clutch_id
left join crosses_union x on x.clutch_id = b.clutch_id
order by coalesce(b.date_birth::timestamp, b.created_at) desc nulls last;

COMMIT;
