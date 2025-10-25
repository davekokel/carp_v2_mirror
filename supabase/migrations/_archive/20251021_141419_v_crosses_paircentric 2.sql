begin;

create or replace view public.v_crosses as
with runs as (
  select
    ci.tank_pair_id as pair_id,
    tp.tank_pair_code as cross_code,
    vtm.fish_code as mom_code,
    vtf.fish_code as dad_code,
    count(*)::int as n_runs,
    max(ci.cross_date) as latest_cross_date,
    min(ci.created_by) as created_by,
    min(ci.created_at) as created_at
  from public.cross_instances ci
  left join public.tank_pairs tp on tp.id = ci.tank_pair_id
  left join public.v_tanks vtm on vtm.tank_id = tp.mother_tank_id
  left join public.v_tanks vtf on vtf.tank_id = tp.father_tank_id
  group by ci.tank_pair_id, tp.tank_pair_code, vtm.fish_code, vtf.fish_code
),
planned_only as (
  select
    tp.id as pair_id,
    tp.tank_pair_code as cross_code,
    vtm.fish_code as mom_code,
    vtf.fish_code as dad_code,
    0::int as n_runs,
    null::date as latest_cross_date,
    cp.created_by,
    cp.created_at
  from public.clutch_plans cp
  join public.tank_pairs tp on tp.id = cp.tank_pair_id
  left join public.v_tanks vtm on vtm.tank_id = tp.mother_tank_id
  left join public.v_tanks vtf on vtf.tank_id = tp.father_tank_id
  where not exists (select 1 from runs r2 where r2.pair_id is not distinct from tp.id)
)
select
  r.pair_id as cross_id,
  r.cross_code as cross_code,
  r.mom_code as mom_code,
  r.dad_code as dad_code,
  coalesce(vs.status,'draft') as status,
  r.n_runs as n_runs,
  r.latest_cross_date as latest_cross_date,
  0::int as n_clutches,
  0::int as n_containers,
  r.created_by as created_by,
  r.created_at as created_at
from runs r
left join public.v_crosses_status vs on vs.id is not distinct from r.pair_id
union all
select
  p.pair_id as cross_id,
  p.cross_code as cross_code,
  p.mom_code as mom_code,
  p.dad_code as dad_code,
  coalesce(vs.status,'draft') as status,
  p.n_runs as n_runs,
  p.latest_cross_date as latest_cross_date,
  0::int as n_clutches,
  0::int as n_containers,
  p.created_by as created_by,
  p.created_at as created_at
from planned_only p
left join public.v_crosses_status vs on vs.id is not distinct from p.pair_id;

commit;
