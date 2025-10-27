create or replace view public.v_tank_pairs as
select
  tp.tank_pair_code::text as tank_pair_code,
  null::text              as fish_pair_code,
  null::text              as mother_tank_code,
  null::text              as father_tank_code
from public.tank_pairs tp;
