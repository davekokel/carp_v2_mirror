BEGIN;

CREATE OR REPLACE VIEW public.v_clutch_instances AS
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
  ci.id AS clutch_instance_id,
  ci.clutch_instance_code AS clutch_code,
  ci.clutch_genotype_pretty AS clutch_genotype_effective,
  ci.tank_pair_code,
  ci.created_at AS created_at_instance,
  COALESCE(tcount.treatments_count_effective,0) AS treatments_count_effective,
  COALESCE(tagg.treatments_pretty_effective,'') AS treatments_pretty_effective,
  tcount.last_treatment_at
FROM public.clutch_instances ci
LEFT JOIN tcount ON tcount.clutch_instance_id = ci.id
LEFT JOIN tagg  ON tagg.clutch_instance_id  = ci.id;

COMMIT;
