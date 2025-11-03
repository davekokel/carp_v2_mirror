BEGIN;

-- 1) Drop dependent clutch views so we can recreate v_tank_pairs cleanly
DROP VIEW IF EXISTS public.v_clutch_instances CASCADE;
DROP VIEW IF EXISTS public.v_clutch_instances_base CASCADE;

-- 2) Recreate v_tank_pairs with the desired column set
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

-- 3) Rebuild clutch views (tight, normalized; no dependency on v_tank_pairs)
CREATE VIEW public.v_clutch_instances_base AS
SELECT
  c.id                            AS clutch_id,
  c.clutch_instance_code,
  c.cross_instance_id,
  c.tank_pair_code,
  c.clutch_genotype_pretty,
  c.normalized_genotype,
  c.created_at                    AS clutch_created_at,
  r.treatment_id,
  r.treatment_name_resolved       AS treatment_name,
  r.treatment_code_resolved       AS treatment_code,
  r.kind_code                     AS treatment_kind_code,
  r.treatment_notes,
  r.created_at                    AS last_treatment_at
FROM public.clutches c
LEFT JOIN public.v_join_clutch_treatments_resolved r
  ON r.clutch_instance_id = c.id;

CREATE VIEW public.v_clutch_instances AS
SELECT * FROM public.v_clutch_instances_base;

COMMIT;
