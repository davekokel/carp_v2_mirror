drop view if exists public.v_cross_clutch_instances;

create view public.v_cross_clutch_instances as
select
  x.id::uuid                     as cross_instance_id,
  x.cross_run_code::text         as cross_code,
  x.tank_pair_code::text         as tank_pair_code,
  tp.fish_pair_code::text        as fish_pair_code,
  tp.mom_fish_code::text         as mom_fish_code,
  tp.dad_fish_code::text         as dad_fish_code,
  tp.mother_tank_code::text      as mom_tank_code,
  tp.father_tank_code::text      as dad_tank_code,
  (x.cross_date)::date           as cross_date,
  x.created_at::timestamptz      as cross_created_at,
  ci.id::uuid                    as clutch_instance_id,
  ci.clutch_instance_code::text  as clutch_code,
  ci.created_at::timestamptz     as clutch_created_at
from public.cross_instances x
left join public.v_tank_pairs tp on tp.tank_pair_code = x.tank_pair_code
left join public.clutch_instances ci on ci.cross_instance_id = x.id;
