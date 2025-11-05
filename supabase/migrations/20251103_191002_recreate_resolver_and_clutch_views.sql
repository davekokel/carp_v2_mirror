BEGIN;

-- Always drop the dependent views before recreating
DROP VIEW IF EXISTS public.v_clutch_instances;
DROP VIEW IF EXISTS public.v_clutch_instances_resolved_compat;

-- Recreate v_clutch_instances from the guarded base view
CREATE VIEW public.v_clutch_instances AS
SELECT
  clutch_id,
  clutch_code,
  clutch_genotype_pretty,
  clutch_instance_id,
  clutch_instance_code,
  created_at
FROM public.v_clutch_instances_base_resolved;

-- If you keep a compat view, make it an alias of the guarded one too
CREATE VIEW public.v_clutch_instances_resolved_compat AS
SELECT
  clutch_id,
  clutch_code,
  clutch_genotype_pretty,
  clutch_instance_id,
  clutch_instance_code,
  created_at
FROM public.v_clutch_instances_base_resolved;

COMMIT;
