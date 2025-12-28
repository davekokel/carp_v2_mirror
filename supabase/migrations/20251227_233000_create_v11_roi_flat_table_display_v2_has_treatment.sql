CREATE OR REPLACE VIEW public.v11_roi_flat_table_display_v2 AS
SELECT
  t.*,
  (
    (t.treated_clutch_code IS NOT NULL AND btrim(t.treated_clutch_code) <> '')
    OR (t.treatment_code IS NOT NULL AND btrim(t.treatment_code) <> '')
    OR (t.plasmids_display IS NOT NULL AND btrim(t.plasmids_display) <> '')
    OR (t.rnas_display IS NOT NULL AND btrim(t.rnas_display) <> '')
    OR (t.dyes_display IS NOT NULL AND btrim(t.dyes_display) <> '')
  ) AS has_treatment
FROM public.v11_roi_treatment_table_display t;
