BEGIN;

CREATE OR REPLACE VIEW public.v_roi_overview_rollups AS
WITH treatment_styles AS (
  SELECT
    t.treat_code,

    (
      SELECT string_agg(s.tok, '; ' ORDER BY s.tok)
      FROM (
        SELECT DISTINCT
          ((tmc.delivery_form || '(') || lower(c.base_code) || ')') AS tok
        FROM public.treatment_mixes tm
        JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
        JOIN public.constructs c ON c.id = tmc.construct_id
        WHERE tm.treatment_id = t.id
      ) s
      WHERE s.tok IS NOT NULL AND btrim(s.tok) <> ''
    ) AS treatment_basecodes_typed,

    (
      SELECT string_agg(s.tok, '; ' ORDER BY s.tok)
      FROM (
        SELECT DISTINCT
          (tmc.delivery_form || '(' || cms.fluortag_style || ')') AS tok
        FROM public.treatment_mixes tm
        JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
        JOIN public.constructs c ON c.id = tmc.construct_id
        JOIN public.v_construct_marker_styles cms ON cms.base_code = lower(btrim(c.base_code))
        WHERE tm.treatment_id = t.id
          AND cms.fluortag_style IS NOT NULL
          AND btrim(cms.fluortag_style) <> ''
      ) s
      WHERE s.tok IS NOT NULL AND btrim(s.tok) <> ''
    ) AS treatment_fluortag_style,

    (
      SELECT string_agg(s.tok, '; ' ORDER BY s.tok)
      FROM (
        SELECT DISTINCT
          (tmc.delivery_form || '(' || cms.fluororganelle_style || ')') AS tok
        FROM public.treatment_mixes tm
        JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
        JOIN public.constructs c ON c.id = tmc.construct_id
        JOIN public.v_construct_marker_styles cms ON cms.base_code = lower(btrim(c.base_code))
        WHERE tm.treatment_id = t.id
          AND cms.fluororganelle_style IS NOT NULL
          AND btrim(cms.fluororganelle_style) <> ''
      ) s
      WHERE s.tok IS NOT NULL AND btrim(s.tok) <> ''
    ) AS treatment_fluororganelle_style

  FROM public.treatments t
),
geno_display AS (
  SELECT
    v1.roi_id,
    COALESCE(
      NULLIF(btrim(v1.genotype_tg_style), ''),
      NULLIF(btrim(v1.genotype_pretty), ''),
      NULLIF(btrim(v1.genotype_basecodes), ''),
      NULLIF(btrim(cl.genetic_background), '')
    ) AS genotype_display,
    NULLIF(btrim(v1.genotype_fluortag_style), '') AS geno_fluortag,
    NULLIF(btrim(v1.genotype_fluororganelle_style), '') AS geno_fluororganelle
  FROM public.v_roi_overview v1
  LEFT JOIN public.clutches cl ON cl.clutch_code = v1.clutch_code
)
SELECT
  v.roi_id,
  v.plate_id,
  v.plate_code,
  v.experiment_date,
  v.experiment_name,
  v.plate_note,
  v.slot_id,
  v.slot_label,
  v.slot_index,
  v.slot_note,
  v.roi_index_within_slot,
  v.roi_code,
  v.roi_note_anatomy,
  v.roi_path,
  v.created_at,
  v.clutch_code,
  v.treated_clutch_code,
  v.treatment_code,
  v.treatment_text,
  v.genotype_code,
  v.genotype_basecodes,
  v.genotype_pretty,
  v.genotype_tg_style,
  v.genotype_fluortag_style,
  v.genotype_fluororganelle_style,
  v.label_tg_style,
  v.label_fluortag_style,
  v.label_fluororganelle_style,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_basecodes_typed), '') <> ''
     AND COALESCE(btrim(gd.genotype_display), '') <> ''
    THEN ts.treatment_basecodes_typed || ' > ' || gd.genotype_display
    WHEN COALESCE(btrim(gd.genotype_display), '') <> ''
    THEN gd.genotype_display
    ELSE NULL
  END AS marker_rollup_tg,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_fluortag_style), '') <> ''
     AND COALESCE(btrim(gd.geno_fluortag), '') <> ''
    THEN ts.treatment_fluortag_style || ' > ' || gd.geno_fluortag
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_fluortag_style), '') <> ''
    THEN ts.treatment_fluortag_style
    ELSE gd.geno_fluortag
  END AS marker_rollup_fluortag,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_fluororganelle_style), '') <> ''
     AND COALESCE(btrim(gd.geno_fluororganelle), '') <> ''
    THEN ts.treatment_fluororganelle_style || ' > ' || gd.geno_fluororganelle
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_fluororganelle_style), '') <> ''
    THEN ts.treatment_fluororganelle_style
    ELSE gd.geno_fluororganelle
  END AS marker_rollup_fluororganelle,

  gd.genotype_display,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_basecodes_typed), '') <> ''
     AND COALESCE(btrim(gd.genotype_display), '') <> ''
    THEN ts.treatment_basecodes_typed || ' > ' || gd.genotype_display
    WHEN COALESCE(btrim(gd.genotype_display), '') <> ''
    THEN gd.genotype_display
    ELSE NULL
  END AS marker_rollup_display_tg,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_fluortag_style), '') <> ''
     AND COALESCE(btrim(gd.geno_fluortag), '') <> ''
    THEN ts.treatment_fluortag_style || ' > ' || gd.geno_fluortag
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_fluortag_style), '') <> ''
    THEN ts.treatment_fluortag_style
    ELSE gd.geno_fluortag
  END AS marker_rollup_display_fluortag,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_fluororganelle_style), '') <> ''
     AND COALESCE(btrim(gd.geno_fluororganelle), '') <> ''
    THEN ts.treatment_fluororganelle_style || ' > ' || gd.geno_fluororganelle
    WHEN COALESCE(btrim(v.treated_clutch_code), '') <> ''
     AND COALESCE(btrim(v.treatment_code), '') <> ''
     AND COALESCE(btrim(ts.treatment_fluororganelle_style), '') <> ''
    THEN ts.treatment_fluororganelle_style
    ELSE gd.geno_fluororganelle
  END AS marker_rollup_display_fluororganelle

FROM public.v_roi_overview v
LEFT JOIN treatment_styles ts ON ts.treat_code = v.treatment_code
LEFT JOIN geno_display gd ON gd.roi_id = v.roi_id;

COMMIT;
