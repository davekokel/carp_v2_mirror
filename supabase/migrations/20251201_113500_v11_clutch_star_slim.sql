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
    jct.clutch_id::text                         AS clutch_id,
    string_agg(DISTINCT t.treat_code, ', ' ORDER BY t.treat_code)       AS treat_codes,
    string_agg(DISTINCT t.kind_code,  ', ' ORDER BY t.kind_code)        AS kind_codes,
    string_agg(DISTINCT tm.mix_code,  ', ' ORDER BY tm.mix_code)        AS mix_codes,
    string_agg(DISTINCT vmf.fluor_codes, ', ' ORDER BY vmf.fluor_codes) AS fluor_codes,
    string_agg(DISTINCT vmf.fluor_names, ', ' ORDER BY vmf.fluor_names) AS fluor_names,
    string_agg(DISTINCT vmf.tag_codes,   ', ' ORDER BY vmf.tag_codes)   AS tag_codes
  FROM public.join_clutch_treatments jct
  LEFT JOIN public.treatments t
    ON t.id = jct.treatment_id
  LEFT JOIN public.treatment_mixes tm
    ON tm.treatment_id = t.id
  LEFT JOIN public.v10_treatment_mix_fluors vmf
    ON vmf.mix_id = tm.id
  GROUP BY jct.clutch_id::text
)
SELECT
  c.id::text                AS clutch_id,
  c.clutch_code,
  c.clutch_date,
  COALESCE(c.genotype_pretty, c.genotype_cross_label) AS genotype,
  c.source_system,

  COALESCE(im.n_imaging_slots, 0) AS n_imaging_slots,
  COALESCE(im.n_rois, 0)          AS n_rois,

  COALESCE(tr.treat_codes,  '') AS treat_codes,
  COALESCE(tr.kind_codes,   '') AS kind_codes,
  COALESCE(tr.mix_codes,    '') AS mix_codes,
  COALESCE(tr.fluor_codes,  '') AS fluor_codes,
  COALESCE(tr.fluor_names,  '') AS fluor_names,
  COALESCE(tr.tag_codes,    '') AS tag_codes

FROM public.clutches c
LEFT JOIN imaging im
  ON im.clutch_id = c.id::text
LEFT JOIN treat tr
  ON tr.clutch_id = c.id::text
ORDER BY c.clutch_date, c.clutch_code;

COMMIT;
