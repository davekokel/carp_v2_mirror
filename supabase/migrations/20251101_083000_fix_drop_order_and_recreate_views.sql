BEGIN;

DROP VIEW IF EXISTS public.v_clutch_instances CASCADE;
DROP VIEW IF EXISTS public.v_clutch_treatments CASCADE;

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
