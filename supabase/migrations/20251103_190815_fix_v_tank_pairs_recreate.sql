BEGIN;

DROP VIEW IF EXISTS public.v_tank_pairs;

CREATE VIEW public.v_tank_pairs AS
SELECT
  tp.id::text                 AS tank_pair_id,
  tp.tank_pair_code,
  tp.status,
  tp.note,
  tp.created_by,
  tp.created_at,
  tp.updated_at,
  tp.mother_tank_id::text     AS mother_tank_id,
  tm.tank_code                AS mother_tank_code,
  tp.father_tank_id::text     AS father_tank_id,
  tf.tank_code                AS father_tank_code
FROM public.tank_pairs tp
LEFT JOIN public.tanks tm ON tm.id=tp.mother_tank_id
LEFT JOIN public.tanks tf ON tf.id=tp.father_tank_id;

COMMIT;
