BEGIN;

DROP VIEW IF EXISTS public.v_clutch_instances_base_resolved;

CREATE VIEW public.v_clutch_instances_base_resolved AS
SELECT
  c.id                          AS clutch_id,
  c.clutch_instance_code,
  c.cross_instance_id,
  c.tank_pair_code,
  c.clutch_genotype_pretty,
  c.normalized_genotype,
  c.created_at                  AS clutch_created_at,
  r.treatment_id,
  r.treatment_name_resolved,
  r.treatment_code_resolved,
  r.kind_code                   AS treatment_kind_code,
  r.treatment_notes,
  r.created_at                  AS treatment_created_at
FROM public.clutches c
LEFT JOIN public.v_join_clutch_treatments_resolved r
  ON r.clutch_instance_id = c.id;

COMMIT;
