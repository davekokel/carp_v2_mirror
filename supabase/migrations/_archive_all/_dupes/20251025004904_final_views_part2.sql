begin;

-- v_tanks
create or replace view public.v_tanks as
select
  t.tank_code,
  t.fish_code,
  f.id         as fish_id,
  t.rack,
  t.position,
  t.created_at,
  t.created_by
from public.tanks t
left join public.fish f
  on f.fish_code = t.fish_code;

-- v_tank_pairs_canonical
create or replace view public.v_tank_pairs_canonical as
with fp as (
  select
    fp.fish_pair_code,
    fp.mom_fish_id,
    fp.dad_fish_id,
    fp.created_at as pair_created_at,
    fm.fish_code  as mom_fish_code,
    fd.fish_code  as dad_fish_code
  from public.fish_pairs fp
  left join public.fish fm on fm.id = fp.mom_fish_id
  left join public.fish fd on fd.id = fp.dad_fish_id
)
select
  tp.tank_pair_code,
  tp.fish_pair_code,
  fp.mom_fish_id,
  fp.dad_fish_id,
  fp.mom_fish_code,
  fp.dad_fish_code,
  mom_t.tank_code as mother_tank_code,
  dad_t.tank_code as father_tank_code,
  tp.created_at   as tank_pair_created_at,
  fp.pair_created_at
from public.tank_pairs tp
left join fp on fp.fish_pair_code = tp.fish_pair_code
left join lateral (
  select t.tank_code
  from public.tanks t
  where t.fish_code = fp.mom_fish_code
  order by t.created_at asc, t.tank_code asc
  limit 1
) mom_t on true
left join lateral (
  select t.tank_code
  from public.tanks t
  where t.fish_code = fp.dad_fish_code
  order by t.created_at asc, t.tank_code asc
  limit 1
) dad_t on true;

-- v_overview_crosses_cx
create or replace view public.v_overview_crosses_cx as
select
  ci.cross_run_code               as cr_code,
  ci.tank_pair_code               as tp_code,
  tp.fish_pair_code               as fp_code,
  c.id                            as cross_id,
  c.created_at                    as cross_created_at,
  c.created_by                    as cross_created_by,
  c.mother_code,
  c.father_code
from public.cross_instances ci
left join public.tank_pairs tp on tp.tank_pair_code = ci.tank_pair_code
left join public.crosses     c  on c.id = ci.cross_id;

-- v_overview_clutches_cx
create or replace view public.v_overview_clutches_cx as
select
  cli.clutch_instance_code        as cl_inst_code,
  ci.cross_run_code               as cr_code,
  cli.tank_pair_code              as tp_code,
  tp.fish_pair_code               as fp_code,
  c.id                            as cross_id,
  cl.id                           as clutch_id,
  cl.clutch_code                  as cl_code,
  cli.created_at                  as cl_inst_created_at,
  cl.created_at                   as cl_created_at
from public.clutch_instances cli
left join public.cross_instances ci on ci.tank_pair_code = cli.tank_pair_code
left join public.tank_pairs     tp on tp.tank_pair_code = cli.tank_pair_code
left join public.crosses        c  on c.id = ci.cross_id
left join public.clutches       cl on cl.cross_id = c.id;

commit;
