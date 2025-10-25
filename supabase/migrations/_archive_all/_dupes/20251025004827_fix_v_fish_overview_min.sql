begin;

create or replace view public.v_fish_overview_min as
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
  f.id,
  f.fish_code,
  f.created_at,
  f.created_by,
  ft.first_tank_code,
  ft.first_tank_at,
  coalesce(tc.n_tanks, 0) as n_tanks
from public.fish f
left join first_tank  ft on ft.fish_code = f.fish_code
left join tank_counts tc on tc.fish_code = f.fish_code;

commit;
