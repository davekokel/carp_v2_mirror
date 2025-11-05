BEGIN;

-- Do not drop the base view; we will replace it in-place.
-- DROP VIEW IF EXISTS public.v_clutch_instances_base_resolved;
DROP VIEW IF EXISTS public.v_clutch_instances;
DROP VIEW IF EXISTS public.v_clutch_instances_resolved_compat;

DO $$
DECLARE
  has_geno boolean;
  has_ci_fk boolean;
  sql_base text;
  join_clause text;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutches' AND column_name='clutch_genotype_pretty'
  ) INTO has_geno;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_id'
  ) INTO has_ci_fk;

  IF has_ci_fk THEN
    join_clause := 'LEFT JOIN public.clutch_instances ci ON ci.clutch_id = c.id';
  ELSE
    join_clause := 'LEFT JOIN public.clutch_instances ci ON false';
  END IF;

  sql_base := format($s$
    CREATE OR REPLACE VIEW public.v_clutch_instances_base_resolved AS
    SELECT
      c.id                                   AS clutch_id,
      c.clutch_code                          AS clutch_code,
      %s                                     AS clutch_genotype_pretty,
      ci.id                                  AS clutch_instance_id,
      ci.clutch_instance_code                AS clutch_instance_code,
      COALESCE(ci.created_at, c.created_at)  AS created_at
    FROM public.clutches c
    %s;
  $s$,
    CASE WHEN has_geno THEN 'c.clutch_genotype_pretty' ELSE 'NULL::text' END,
    join_clause
  );

  EXECUTE sql_base;

  -- Recreate child views from the base view so they inherit the guards
  CREATE VIEW public.v_clutch_instances AS
  SELECT clutch_id, clutch_code, clutch_genotype_pretty, clutch_instance_id, clutch_instance_code, created_at
  FROM public.v_clutch_instances_base_resolved;

  CREATE VIEW public.v_clutch_instances_resolved_compat AS
  SELECT clutch_id, clutch_code, clutch_genotype_pretty, clutch_instance_id, clutch_instance_code, created_at
  FROM public.v_clutch_instances_base_resolved;

END$$;

COMMIT;
