BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_star;

CREATE VIEW public.v11_clutch_star AS
WITH imaging AS (
  SELECT
    v.clutch_id,
    v.clutch_code,
    v.clutch_date,
    v.estimated_egg_count,
    COUNT(DISTINCT v.slot_id) AS n_imaging_slots,
    COUNT(v.roi_id)           AS n_rois,
    STRING_AGG(
      DISTINCT v.fish_genotype_pretty,
      ' | ' ORDER BY v.fish_genotype_pretty
    ) AS genotype_pretty
  FROM public.v11_imaging_roi_star v
  GROUP BY
    v.clutch_id,
    v.clutch_code,
    v.clutch_date,
    v.estimated_egg_count
),
treats AS (
  SELECT
    jct.clutch_id::text AS clutch_id,
    STRING_AGG(DISTINCT t.treat_code, ', ' ORDER BY t.treat_code) AS treat_codes,
    STRING_AGG(DISTINCT tmf.fluor_codes, ', ' ORDER BY tmf.fluor_codes) AS treat_fluor_tag,
    STRING_AGG(DISTINCT tmf.fluor_names, ', ' ORDER BY tmf.fluor_names) AS treat_organelle_fluor
  FROM public.join_clutch_treatments jct
  JOIN public.treatments t
    ON t.id = jct.treatment_id
  JOIN public.treatment_mixes tm
    ON tm.treatment_id = t.id
  LEFT JOIN public.v10_treatment_mix_fluors tmf
    ON tmf.mix_id = tm.id
  GROUP BY jct.clutch_id::text
)
SELECT
  c.id::text           AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  c.estimated_egg_count,
  i.n_imaging_slots,
  i.n_rois,
  i.genotype_pretty,
  treats.treat_codes,
  treats.treat_fluor_tag,
  treats.treat_organelle_fluor
FROM public.clutches c
LEFT JOIN imaging i
  ON i.clutch_id = c.id::text
LEFT JOIN treats
  ON treats.clutch_id = c.id::text
ORDER BY c.clutch_date, c.clutch_code;

COMMIT;
