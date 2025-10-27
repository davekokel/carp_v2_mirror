DROP VIEW IF EXISTS public.v_clutches_overview;

CREATE VIEW public.v_clutches_overview AS
WITH tcounts AS (
  SELECT
    ct.clutch_id,
    COUNT(*)::int AS treatments_count,
    MAX(ct.at_time) AS last_treatment_at,
    STRING_AGG(
      COALESCE(ct.type || ':' || ct.note, ct.type),
      '; ' ORDER BY ct.at_time DESC NULLS LAST
    ) AS treatments_pretty
  FROM public.clutch_treatments ct
  GROUP BY ct.clutch_id
)
SELECT
  ci.id AS clutch_instance_id,
  ci.clutch_instance_code,
  ci.label AS clutch_label,
  ci.phenotype,
  ci.notes,
  ci.red_selected,
  ci.green_selected,
  ci.cross_instance_id,
  ci.created_at,
  ci.updated_at,
  ci.tank_pair_code,
  tc.treatments_count,
  tc.treatments_pretty,
  tc.last_treatment_at
FROM public.clutch_instances ci
LEFT JOIN tcounts tc ON tc.clutch_id = ci.id;
