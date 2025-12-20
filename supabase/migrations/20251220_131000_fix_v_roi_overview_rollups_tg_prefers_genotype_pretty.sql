BEGIN;

CREATE OR REPLACE VIEW public.v_roi_overview_rollups AS
WITH treatment_styles AS (
  SELECT
    t.treat_code,
    (
      SELECT string_agg(s.tok, '; ' ORDER BY s.tok)
      FROM (
        SELECT DISTINCT
          (tmc.delivery_form || '(' || lower(c.base_code) || ')') AS tok
        FROM public.treatment_mixes tm
        JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
        JOIN public.constructs c ON c.id = tmc.construct_id
        WHERE tm.treatment_id = t.id
      ) s
      WHERE s.tok IS NOT NULL AND btrim(s.tok) <> ''
    ) AS treatment_tg_style,
    (
      SELECT string_agg(s.tok, '; ' ORDER BY s.tok)
      FROM (
        SELECT DISTINCT
          (tmc.delivery_form || '(' || COALESCE(vcms.fluortag_style, lower(c.base_code)) || ')') AS tok
        FROM public.treatment_mixes tm
        JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
        JOIN public.constructs c ON c.id = tmc.construct_id
        LEFT JOIN public.v_construct_marker_styles vcms ON vcms.base_code = lower(btrim(c.base_code))
        WHERE tm.treatment_id = t.id
      ) s
      WHERE s.tok IS NOT NULL AND btrim(s.tok) <> ''
    ) AS treatment_fluortag_style,
    (
      SELECT string_agg(s.tok, '; ' ORDER BY s.tok)
      FROM (
        SELECT DISTINCT
          (tmc.delivery_form || '(' || COALESCE(vcms.fluororganelle_style, lower(c.base_code)) || ')') AS tok
        FROM public.treatment_mixes tm
        JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
        JOIN public.constructs c ON c.id = tmc.construct_id
        LEFT JOIN public.v_construct_marker_styles vcms ON vcms.base_code = lower(btrim(c.base_code))
        WHERE tm.treatment_id = t.id
      ) s
      WHERE s.tok IS NOT NULL AND btrim(s.tok) <> ''
    ) AS treatment_fluororganelle_style
  FROM public.treatments t
),
geno_display AS (
  SELECT
    v.roi_id,

    COALESCE(
      NULLIF(btrim(v.genotype_pretty), ''),
      NULLIF(btrim(v.genotype_basecodes), ''),
      NULLIF(btrim(v.genotype_tg_style), '')
    ) AS geno_tg,

    NULLIF(btrim(v.genotype_fluortag_style), '') AS geno_fluortag,
    NULLIF(btrim(v.genotype_fluororganelle_style), '') AS geno_fluororganelle,

    COALESCE(
      NULLIF(btrim(v.genotype_pretty), ''),
      NULLIF(btrim(v.genotype_basecodes), ''),
      NULLIF(btrim(v.genotype_tg_style), '')
    ) AS genotype_display
  FROM public.v_roi_overview v
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
     AND COALESCE(btrim(ts.treatment_tg_style), '') <> ''
     AND COALESCE(btrim(gd.geno_tg), '') <> ''
    THEN ts.treatment_tg_style || ' > ' || gd.geno_tg
    WHEN COALESCE(btrim(gd.geno_tg), '') <> ''
    THEN gd.geno_tg
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
     AND COALESCE(btrim(ts.treatment_tg_style), '') <> ''
     AND COALESCE(btrim(gd.geno_tg), '') <> ''
    THEN ts.treatment_tg_style || ' > ' || gd.geno_tg
    WHEN COALESCE(btrim(gd.geno_tg), '') <> ''
    THEN gd.geno_tg
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
