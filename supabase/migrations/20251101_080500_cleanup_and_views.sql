BEGIN;

-- Always clear the two dependent views first
DROP VIEW IF EXISTS public.v_clutch_instances CASCADE;
DROP VIEW IF EXISTS public.v_clutch_treatments CASCADE;

-- Drop transgene_allele_registry regardless of whether it's a table/view/matview (or absent)
DO $$
DECLARE
  objkind char;
BEGIN
  SELECT c.relkind INTO objkind
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relname = 'transgene_allele_registry';

  IF objkind = 'v' THEN
    EXECUTE 'DROP VIEW public.transgene_allele_registry';
  ELSIF objkind = 'm' THEN
    EXECUTE 'DROP MATERIALIZED VIEW public.transgene_allele_registry';
  ELSIF objkind IN ('r','p') THEN
    EXECUTE 'DROP TABLE public.transgene_allele_registry CASCADE';
  END IF;
END $$;

-- Drop the other legacy tables if present
DROP TABLE IF EXISTS public.fish_tank_memberships CASCADE;
DROP TABLE IF EXISTS public.containers CASCADE;
DROP TABLE IF EXISTS public.clutch_materials CASCADE;

-- Recreate views
CREATE VIEW public.v_clutch_treatments AS
SELECT
  t.id,
  t.clutch_instance_id,
  ci.clutch_instance_code,
  ci.tank_pair_code,
  t.material_type,
  t.material_code,
  t.material_name,
  t.notes,
  t.created_by,
  t.created_at
FROM public.treatments t
LEFT JOIN public.clutch_instances ci ON ci.id = t.clutch_instance_id;

CREATE VIEW public.v_clutch_instances (
  clutch_instance_id,
  clutch_code,
  clutch_genotype_effective,
  tank_pair_code,
  created_at_instance,
  treatments_count_effective,
  treatments_pretty_effective,
  last_treatment_at
) AS
WITH tcount AS (
  SELECT
    clutch_instance_id,
    COUNT(*)::int AS treatments_count_effective,
    MAX(created_at) AS last_treatment_at
  FROM public.treatments
  GROUP BY clutch_instance_id
),
tdist AS (
  SELECT
    clutch_instance_id,
    mat_pretty
  FROM (
    SELECT
      clutch_instance_id,
      CONCAT_WS(' ',
        COALESCE(material_type,''),
        COALESCE(material_code,''),
        COALESCE(material_name,'')
      )::text AS mat_pretty
    FROM public.treatments
  ) s
  WHERE NULLIF(mat_pretty,'') IS NOT NULL
  GROUP BY clutch_instance_id, mat_pretty
),
tagg AS (
  SELECT
    clutch_instance_id,
    string_agg(mat_pretty, ', ' ORDER BY mat_pretty) AS treatments_pretty_effective
  FROM tdist
  GROUP BY clutch_instance_id
)
SELECT
  ci.id,
  ci.clutch_instance_code,
  ci.clutch_genotype_pretty,
  ci.tank_pair_code,
  ci.created_at,
  COALESCE(tcount.treatments_count_effective,0),
  COALESCE(tagg.treatments_pretty_effective,''),
  tcount.last_treatment_at
FROM public.clutch_instances ci
LEFT JOIN tcount ON tcount.clutch_instance_id = ci.id
LEFT JOIN tagg  ON tagg.clutch_instance_id  = ci.id;

COMMIT;
