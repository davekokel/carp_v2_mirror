BEGIN;

DROP VIEW IF EXISTS public.v_clutch_instances_clean_compat;
DROP VIEW IF EXISTS public.v_clutch_instances_clean;
DROP VIEW IF EXISTS public.v_clutch_instances_resolved_compat;
DROP VIEW IF EXISTS public.v_clutch_instances;

CREATE VIEW public.v_clutch_instances AS
SELECT
  clutch_id,
  clutch_code,
  clutch_genotype_pretty,
  clutch_instance_id,
  clutch_instance_code,
  created_at
FROM public.v_clutch_instances_base_resolved;

CREATE VIEW public.v_clutch_instances_clean AS
SELECT
  clutch_id,
  clutch_code,
  COALESCE(clutch_genotype_pretty,'') AS clutch_genotype_pretty,
  clutch_instance_id,
  COALESCE(clutch_instance_code,'')   AS clutch_instance_code,
  created_at
FROM public.v_clutch_instances;

CREATE VIEW public.v_clutch_instances_clean_compat AS
SELECT
  clutch_id,
  clutch_code,
  clutch_genotype_pretty,
  clutch_instance_id,
  clutch_instance_code,
  created_at
FROM public.v_clutch_instances_clean;

CREATE VIEW public.v_clutch_instances_resolved_compat AS
SELECT
  clutch_id,
  clutch_code,
  clutch_genotype_pretty,
  clutch_instance_id,
  clutch_instance_code,
  created_at
FROM public.v_clutch_instances;

COMMIT;
