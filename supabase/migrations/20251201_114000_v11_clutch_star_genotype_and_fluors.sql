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
tr_raw AS (
  -- expand treatments out to constructs/fusions/fluors/tags
  SELECT
    jct.clutch_id::text AS clutch_id,
    t.treat_code,
    t.kind_code,
    tm.mix_code,
    fl.fluor_code,
    tg.tag_code,
    f.tag_pos,
    tg.localization
  FROM public.join_clutch_treatments jct
  LEFT JOIN public.treatments t
    ON t.id = jct.treatment_id
  LEFT JOIN public.treatment_mixes tm
    ON tm.treatment_id = t.id
  LEFT JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
  LEFT JOIN public.constructs c
    ON c.id = tmc.construct_id
  LEFT JOIN public.construct_fusions cf
    ON cf.construct_id = c.id
  LEFT JOIN public.fusions f
    ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl
    ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg
    ON tg.id = f.tag_id
),
treat AS (
  SELECT
    clutch_id,
    -- simple codes/kinds/mixes
    string_agg(DISTINCT treat_code, ', ' ORDER BY treat_code) AS treat_codes,
    string_agg(DISTINCT kind_code,  ', ' ORDER BY kind_code)  AS kind_codes,
    string_agg(DISTINCT mix_code,   ', ' ORDER BY mix_code)   AS mix_codes,

    -- fluor::tag(tag_pos)
    string_agg(
      DISTINCT
        CASE
          WHEN fluor_code IS NOT NULL THEN
            fluor_code ||
            CASE
              WHEN tag_code IS NOT NULL THEN '::' || tag_code
              ELSE ''
            END ||
            CASE
              WHEN tag_pos IS NOT NULL THEN '(' || tag_pos || ')'
              ELSE ''
            END
          ELSE NULL
        END,
      ' + '
    ) FILTER (WHERE fluor_code IS NOT NULL) AS treat_fluor_tag,

    -- organelle-fluor
    string_agg(
      DISTINCT
        CASE
          WHEN localization IS NOT NULL AND fluor_code IS NOT NULL THEN
            localization || '-' || fluor_code
          ELSE NULL
        END,
      ' + '
    ) FILTER (WHERE localization IS NOT NULL AND fluor_code IS NOT NULL) AS treat_organelle_fluor
  FROM tr_raw
  GROUP BY clutch_id
)
SELECT
  c.id::text                AS clutch_id,
  c.clutch_code,
  c.clutch_date,

  -- keep both genotype_pretty and cross_label; no COALESCE
  c.genotype_pretty,
  c.genotype_cross_label,
  c.source_system,

  imaging.n_imaging_slots,
  imaging.n_rois,

  treat.treat_codes,
  treat.kind_codes,
  treat.mix_codes,
  treat.treat_fluor_tag,
  treat.treat_organelle_fluor

FROM public.clutches c
LEFT JOIN imaging
  ON imaging.clutch_id = c.id::text
LEFT JOIN treat
  ON treat.clutch_id = c.id::text
ORDER BY c.clutch_date, c.clutch_code;

COMMIT;
