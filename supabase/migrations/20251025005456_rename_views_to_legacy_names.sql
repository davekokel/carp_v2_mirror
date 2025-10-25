begin;

-- 1) v_fish  (legacy)  ← final definition from v_fish_overview_min
drop view if exists public.v_fish cascade;
create or replace view public.v_fish as
with first_tank as (
  select distinct on (t.fish_code)
         t.fish_code,
         t.tank_code  as first_tank_code,
         t.created_at as first_tank_at
  from public.tanks t
  where t.fish_code is not null and t.fish_code <> ''
  order by t.fish_code, t.created_at asc, t.tank_code asc
),
tank_counts as (
  select fish_code, count(*)::int as n_tanks
  from public.tanks
  where fish_code is not null and fish_code <> ''
  group by fish_code
)
select
  f.id            as fish_id,
  f.fish_code,
  f.created_at,
  f.created_by,
  ft.first_tank_code,
  ft.first_tank_at,
  coalesce(tc.n_tanks, 0) as n_tanks
from public.fish f
left join first_tank  ft on ft.fish_code = f.fish_code
left join tank_counts tc on tc.fish_code = f.fish_code;

-- 2) v_crosses  (legacy)  ← final definition from v_overview_crosses_cx
drop view if exists public.v_crosses cascade;
create or replace view public.v_crosses as
select
  ci.cross_run_code               as cr_code,
  ci.cross_run_code               as cross_code,   -- legacy column name
  ci.tank_pair_code               as tp_code,
  tp.fish_pair_code               as fp_code,
  c.id                            as cross_id,
  c.created_at                    as created_at,
  c.created_by                    as created_by,
  c.mother_code,
  c.father_code
from public.cross_instances ci
left join public.tank_pairs tp on tp.tank_pair_code = ci.tank_pair_code
left join public.crosses     c  on c.id = ci.cross_id;

-- 3) v_cross_runs (legacy) ← run-centric slice
drop view if exists public.v_cross_runs cascade;
create or replace view public.v_cross_runs as
select
  cr_code,
  tp_code,
  fp_code,
  created_at
from public.v_crosses;

-- 4) Drop the newer names to avoid duplicates (optional)
drop view if exists public.v_fish_overview_min;
drop view if exists public.v_overview_crosses_cx;
-- keep v_overview_clutches_cx unless you also want a v_clutches legacy name

commit;
