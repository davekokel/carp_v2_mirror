BEGIN;

-- 1) Drop dependent views so column drops won't fail
DROP VIEW IF EXISTS public.v_clutch_instances CASCADE;
DROP VIEW IF EXISTS public.v_clutch_instances_base CASCADE;
DROP VIEW IF EXISTS public.v_clutch_instances_base_resolved CASCADE;
DROP VIEW IF EXISTS public.v_join_clutch_treatments_resolved CASCADE;

-- 2) Drop "norm" columns first (they depend on base columns)
ALTER TABLE public.join_clutch_treatments DROP COLUMN IF EXISTS treatment_type_norm;
ALTER TABLE public.join_clutch_treatments DROP COLUMN IF EXISTS treatment_code_norm;

-- 3) Drop legacy base columns
ALTER TABLE public.join_clutch_treatments DROP COLUMN IF EXISTS treatment_name;
ALTER TABLE public.join_clutch_treatments DROP COLUMN IF EXISTS treatment_code;

-- 4) Recreate the resolver with NO legacy fallbacks
CREATE VIEW public.v_join_clutch_treatments_resolved AS
SELECT
  j.id,
  j.clutch_instance_id,
  j.treatment_id,
  t.name         AS treatment_name_resolved,
  t.plasmid_code AS treatment_code_resolved,
  t.kind_code,
  t.notes        AS treatment_notes,
  j.created_at
FROM public.join_clutch_treatments j
LEFT JOIN public.treatments t ON t.id = j.treatment_id;

-- 5) Rebuild tight clutch views on normalized data only
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
