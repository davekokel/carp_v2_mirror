BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_treated_groups_flat;

CREATE VIEW public.v11_clutch_treated_groups_flat AS
SELECT
  treated_clutch_id,
  treated_clutch_code,
  clutch_id,
  clutch_code,
  clutch_date,
  genotype_pretty,
  genotype_basecodes,
  treatment_code,
  marker_basecode_style,
  marker_fluortag_style,
  marker_organelle_style,
  CASE
    WHEN level = 'treated_clutch' THEN treated_clutch_code
    ELSE clutch_code
  END AS assign_code
FROM public.v11_clutch_flat_overview
WHERE level IN ('clutch', 'treated_clutch')
  AND COALESCE(source_system, '') <> 'legacy_imaging';

COMMENT ON VIEW public.v11_clutch_treated_groups_flat IS
'Flat v11 imaging groups for plate assignment: one row per clutch or treated_clutch from v11_clutch_flat_overview, with marker_* styles and assign_code (treated_clutch_code or clutch_code).';

COMMIT;
