BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_treated_groups_flat;

CREATE VIEW public.v11_clutch_treated_groups_flat AS
SELECT
  f.treated_clutch_id,
  f.treated_clutch_code,
  f.clutch_id,
  f.clutch_code,
  f.clutch_date,
  f.genotype_pretty,
  f.genotype_basecodes,
  f.treatment_code,
  f.marker_basecode_style,
  f.marker_fluortag_style,
  f.marker_organelle_style,
  CASE
    WHEN f.level = 'treated_clutch' THEN f.treated_clutch_code
    ELSE f.clutch_code
  END AS assign_code
FROM public.v11_clutch_flat_overview f
JOIN public.clutches c
  ON c.id = f.clutch_id
WHERE f.level IN ('clutch', 'treated_clutch')
  AND COALESCE(c.source_system, '') <> 'legacy_imaging';

COMMENT ON VIEW public.v11_clutch_treated_groups_flat IS
'Flat v11 imaging groups for plate assignment: one row per clutch or treated_clutch from v11_clutch_flat_overview, with marker_* styles and assign_code (treated_clutch_code or clutch_code), excluding legacy_imaging clutches.';

COMMIT;
