-- Recreate golden view without changing any existing column names
-- (CREATE OR REPLACE VIEW cannot rename output columns).

CREATE OR REPLACE VIEW public.v_clutch_instances AS
WITH src AS (
  SELECT
    v.*,
    ci.id AS clutch_instance_uuid,
    ci.observed_genotype_pretty,
    ci.expected_genotype_pretty,
    ci.clutch_genotype_pretty
  FROM public.v_clutch_instances_effective v
  JOIN public.clutch_instances ci
    ON ci.clutch_instance_code = v.clutch_code
)
SELECT
  s.*,
  COALESCE(vt.treatments_count_effective, 0)::int           AS treatments_count_effective,
  COALESCE(vt.treatments_pretty_effective, ''::text)         AS treatments_pretty_effective,
  -- coalesced genotype (keeps the same output name the base view used:
  -- if v_clutch_instances_effective already had clutch_genotype_effective,
  -- we only overwrite it if it's empty; otherwise we expose a composed field below)
  COALESCE(
    NULLIF(s.observed_genotype_pretty,''),
    NULLIF(s.expected_genotype_pretty,''),
    NULLIF(s.clutch_genotype_pretty,''),
    NULLIF(s.clutch_genotype_effective,''),
    ''::text
  )                                                          AS clutch_genotype_effective,
  -- composed “Treatments > genotype” under the canonical name already used by pages
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND
         COALESCE(
           NULLIF(s.observed_genotype_pretty,''),
           NULLIF(s.expected_genotype_pretty,''),
           NULLIF(s.clutch_genotype_pretty,''),
           NULLIF(s.clutch_genotype_effective,'')
         ,'' ) <> ''
    THEN vt.treatments_pretty_effective || ' > ' ||
         COALESCE(
           NULLIF(s.observed_genotype_pretty,''),
           NULLIF(s.expected_genotype_pretty,''),
           NULLIF(s.clutch_genotype_pretty,''),
           NULLIF(s.clutch_genotype_effective,'')
         ,'' )
    ELSE COALESCE(vt.treatments_pretty_effective,
                  s.observed_genotype_pretty,
                  s.expected_genotype_pretty,
                  s.clutch_genotype_pretty,
                  s.clutch_genotype_effective,
                  ''::text)
  END                                                        AS treatments_genotype_effective,
  vt.last_treatment_at
FROM src s
LEFT JOIN public.v_clutch_treatments vt
  ON vt.clutch_instance_id = s.clutch_instance_uuid;

COMMENT ON VIEW public.v_clutch_instances IS
  'Golden clutch instances view: joins v_clutch_treatments; coalesces genotype; keeps original column names.';
