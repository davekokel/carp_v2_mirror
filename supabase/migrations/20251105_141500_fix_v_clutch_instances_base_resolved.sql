BEGIN;

DROP VIEW IF EXISTS public.v_clutch_instances_base_resolved;

DO $$
DECLARE
  has_geno boolean;
  sql text;
BEGIN
  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='clutches'
      AND column_name='clutch_genotype_pretty'
  ) INTO has_geno;

  sql := $s$
    CREATE VIEW public.v_clutch_instances_base_resolved AS
    SELECT
      c.id                                   AS clutch_id,
      c.clutch_code                          AS clutch_code,
      %GENO%                                 AS clutch_genotype_pretty,
      ci.id                                  AS clutch_instance_id,
      ci.clutch_instance_code                AS clutch_instance_code,
      COALESCE(ci.created_at, c.created_at)  AS created_at
    FROM public.clutches c
    LEFT JOIN public.clutch_instances ci
      ON ci.clutch_id = c.id;
  $s$;

  IF has_geno THEN
    sql := replace(sql, '%GENO%', 'c.clutch_genotype_pretty');
  ELSE
    sql := replace(sql, '%GENO%', 'NULL::text');
  END IF;

  EXECUTE sql;
END$$;

COMMIT;
