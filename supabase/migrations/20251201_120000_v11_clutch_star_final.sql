BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_star;

CREATE VIEW public.v11_clutch_star AS
WITH imaging AS (
  SELECT
    v.clutch_id,
    v.clutch_code,
    COUNT(DISTINCT v.slot_id) AS n_imaging_slots,
    COUNT(v.roi_id)           AS n_rois
  FROM public.v11_imaging_roi_star v
  WHERE v.clutch_id IS NOT NULL
  GROUP BY v.clutch_id, v.clutch_code
),
treat AS (
  SELECT
    jct.clutch_id::text AS clutch_id,
    string_agg(DISTINCT t.treat_code, ', ' ORDER BY t.treat_code) AS treat_codes,
    string_agg(DISTINCT v11.fluor_tag, ', ' ORDER BY v11.fluor_tag) AS treat_fluor_tag,
    string_agg(DISTINCT v11.organelle_fluor, ', ' ORDER BY v11.organelle_fluor) AS treat_organelle_fluor
  FROM public.join_clutch_treatments jct
  JOIN public.treatments t
    ON t.id = jct.treatment_id
  JOIN public.treatment_mixes tm
    ON tm.treatment_id = t.id
  LEFT JOIN public.v11_treatment_mix_fluors v11
    ON v11.mix_id = tm.id
  GROUP BY jct.clutch_id::text
)
SELECT
  c.id::text                AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  c.genotype_pretty,
  c.genotype_cross_label,
  c.genotype_base_codes,
  c.genotype_allele_codes,
  c.source_system,
  imaging.n_imaging_slots,
  imaging.n_rois,
  treat.treat_codes,
  treat.treat_fluor_tag,
  treat.treat_organelle_fluor
FROM public.clutches c
LEFT JOIN imaging
  ON imaging.clutch_id = c.id::text
LEFT JOIN treat
  ON treat.clutch_id = c.id::text
ORDER BY c.clutch_date, c.clutch_code;

COMMIT;
