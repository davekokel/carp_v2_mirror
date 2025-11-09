BEGIN;

CREATE OR REPLACE VIEW public.v_clutch_instances AS
SELECT
  cl.id                       AS clutch_instance_id,
  cl.clutch_instance_code     AS clutch_code,
  cl.cross_instance_id        AS cross_id,
  cr.tank_pair_code           AS tank_pair_code,   -- drop later if you go ID-only for tank_pairs
  COALESCE(cl.created_at, cr.created_at) AS created_at
FROM public.clutch_instances cl
JOIN public.crosses cr
  ON cr.id = cl.cross_instance_id;

COMMIT;
