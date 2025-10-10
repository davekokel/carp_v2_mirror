BEGIN;

create or replace view public.vw_clutches_concept_overview as
with base as (
  select
    cp.id_uuid                   as clutch_plan_id,
    pc.id_uuid                   as planned_cross_id,
    cp.clutch_code               as clutch_code,
    cp.planned_name              as clutch_name,
    cp.planned_nickname          as clutch_nickname,
    pc.cross_date                as date_planned,
    coalesce(cp.note, pc.note)   as note,
    cp.created_by,
    cp.created_at
  from public.clutch_plans cp
  left join public.planned_crosses pc on pc.clutch_id = cp.id_uuid
),
inst as (
  select
    c.planned_cross_id,
    count(*)::int                         as n_instances,
    max(c.date_birth)                     as latest_date_birth,
    count(c.cross_id)::int                as n_crosses
  from public.clutches c
  group by c.planned_cross_id
),
cont as (
  select
    c.planned_cross_id,
    count(cc.*)::int                      as n_containers
  from public.clutches c
  join public.clutch_containers cc on cc.clutch_id = c.id_uuid
  group by c.planned_cross_id
)
select
  b.clutch_plan_id,
  b.planned_cross_id,
  b.clutch_code,
  b.clutch_name,
  b.clutch_nickname,
  b.date_planned,
  b.created_by,
  b.created_at,
  b.note,
  coalesce(i.n_instances, 0)              as n_instances,
  coalesce(coalesce(i.n_crosses,0), 0)    as n_crosses,
  coalesce(ct.n_containers, 0)            as n_containers,
  i.latest_date_birth
from base b
left join inst i on i.planned_cross_id = b.planned_cross_id
left join cont ct on ct.planned_cross_id = b.planned_cross_id
order by coalesce(b.date_planned::timestamp, b.created_at) desc nulls last;

COMMIT;
