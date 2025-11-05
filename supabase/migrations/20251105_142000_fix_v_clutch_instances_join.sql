BEGIN;

DROP VIEW IF EXISTS public.v_clutch_instances_clean_compat;
DROP VIEW IF EXISTS public.v_clutch_instances_clean;
DROP VIEW IF EXISTS public.v_clutch_instances_resolved_compat;
DROP VIEW IF EXISTS public.v_clutch_instances;
DROP VIEW IF EXISTS public.v_clutch_instances_base_resolved;

DO $$
DECLARE
  has_ci_clutch_id   bool;
  has_ci_clutch_code bool;
  has_ci_cicode      bool;
  has_c_code         bool;
  sql text;
BEGIN
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_id') INTO has_ci_clutch_id;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_code') INTO has_ci_clutch_code;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_instance_code') INTO has_ci_cicode;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clutches' AND column_name='clutch_code') INTO has_c_code;

  IF has_ci_clutch_id THEN
    sql := $v$
      CREATE VIEW public.v_clutch_instances_base_resolved AS
      SELECT
        c.id                                  AS clutch_id,
        COALESCE(c.clutch_code,'')::text      AS clutch_code,
        NULL::text                            AS clutch_genotype_pretty,
        ci.id                                 AS clutch_instance_id,
        COALESCE(ci.clutch_instance_code,'')  AS clutch_instance_code,
        COALESCE(ci.created_at, c.created_at) AS created_at
      FROM public.clutches c
      LEFT JOIN public.clutch_instances ci ON ci.clutch_id = c.id;
    $v$;
  ELSIF has_ci_clutch_code AND has_c_code THEN
    sql := $v$
      CREATE VIEW public.v_clutch_instances_base_resolved AS
      SELECT
        c.id                                  AS clutch_id,
        COALESCE(c.clutch_code,'')::text      AS clutch_code,
        NULL::text                            AS clutch_genotype_pretty,
        ci.id                                 AS clutch_instance_id,
        COALESCE(ci.clutch_instance_code,'')  AS clutch_instance_code,
        COALESCE(ci.created_at, c.created_at) AS created_at
      FROM public.clutches c
      LEFT JOIN public.clutch_instances ci ON ci.clutch_code = c.clutch_code;
    $v$;
  ELSIF has_ci_cicode AND has_c_code THEN
    sql := $v$
      CREATE VIEW public.v_clutch_instances_base_resolved AS
      SELECT
        c.id                                  AS clutch_id,
        COALESCE(c.clutch_code,'')::text      AS clutch_code,
        NULL::text                            AS clutch_genotype_pretty,
        ci.id                                 AS clutch_instance_id,
        COALESCE(ci.clutch_instance_code,'')  AS clutch_instance_code,
        COALESCE(ci.created_at, c.created_at) AS created_at
      FROM public.clutches c
      LEFT JOIN public.clutch_instances ci ON ci.clutch_instance_code = c.clutch_code;
    $v$;
  ELSE
    RAISE EXCEPTION 'No compatible join keys between clutches and clutch_instances';
  END IF;

  EXECUTE sql;
END$$;

CREATE VIEW public.v_clutch_instances AS
SELECT clutch_id, clutch_code, clutch_genotype_pretty, clutch_instance_id, clutch_instance_code, created_at
FROM public.v_clutch_instances_base_resolved;

CREATE VIEW public.v_clutch_instances_clean AS
SELECT clutch_id, clutch_code,
       COALESCE(clutch_genotype_pretty,'') AS clutch_genotype_pretty,
       clutch_instance_id,
       COALESCE(clutch_instance_code,'')   AS clutch_instance_code,
       created_at
FROM public.v_clutch_instances;

CREATE VIEW public.v_clutch_instances_clean_compat AS
SELECT clutch_id, clutch_code, clutch_genotype_pretty, clutch_instance_id, clutch_instance_code, created_at
FROM public.v_clutch_instances_clean;

CREATE VIEW public.v_clutch_instances_resolved_compat AS
SELECT clutch_id, clutch_code, clutch_genotype_pretty, clutch_instance_id, clutch_instance_code, created_at
FROM public.v_clutch_instances;

COMMIT;
