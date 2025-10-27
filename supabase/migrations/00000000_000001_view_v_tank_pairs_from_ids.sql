create or replace view public.v_tank_pairs as
select
  tp.tank_pair_code::text as tank_pair_code,
  tm.tank_code::text      as mother_tank_code,
  tf.tank_code::text      as father_tank_code
from public.tank_pairs tp
left join public.tanks tm on tm.id = tp.mother_tank_id
left join public.tanks tf on tf.id = tp.father_tank_id;
