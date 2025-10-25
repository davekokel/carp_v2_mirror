begin;

create or replace view public.v_cross_runs as
select
  ci.id                             as cross_instance_id,
  ci.tank_pair_id                   as pair_id,
  tp.tank_pair_code                 as cross_code,
  coalesce(nullif(ci.cross_run_code,''), ci.id::text) as cross_run_code,
  ci.cross_date,
  ci.created_by                     as run_created_by,
  ci.created_at                     as run_created_at,
  vt_m.tank_code                    as mother_tank_label,
  vt_f.tank_code                    as father_tank_label,
  vt_m.fish_code                    as mom_code,
  vt_f.fish_code                    as dad_code,
  coalesce(nullif(ci.note,''), null) as run_note
from public.cross_instances ci
left join public.tank_pairs tp   on tp.id = ci.tank_pair_id
left join public.v_tanks vt_m    on vt_m.tank_id = tp.mother_tank_id
left join public.v_tanks vt_f    on vt_f.tank_id = tp.father_tank_id;

commit;
