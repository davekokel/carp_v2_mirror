BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview_rollups;

CREATE VIEW public.v_roi_overview_rollups AS
WITH treatment_tokens AS (
  SELECT
    t.treat_code,
    (
      SELECT string_agg(s.tok, ';' ORDER BY s.tok)
      FROM (
        SELECT DISTINCT
          CASE
            WHEN tmc.delivery_form IS NULL OR btrim(tmc.delivery_form) = '' THEN NULL
            ELSE (tmc.delivery_form || '(' || c.base_code || ')')
          END AS tok
        FROM public.treatment_mixes tm
        JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
        JOIN public.constructs c ON c.id = tmc.construct_id
        WHERE tm.treatment_id = t.id
      ) s
      WHERE s.tok IS NOT NULL AND btrim(s.tok) <> ''
    ) AS treatment_basecodes_typed
  FROM public.treatments t
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
    WHEN v.treated_clutch_code IS NOT NULL AND btrim(v.treated_clutch_code) <> ''
     AND v.treatment_code IS NOT NULL AND btrim(v.treatment_code) <> ''
     AND tt.treatment_basecodes_typed IS NOT NULL AND btrim(tt.treatment_basecodes_typed) <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || COALESCE(NULLIF(btrim(v.genotype_tg_style), ''), CASE WHEN v.clutch_code LIKE 'LCL-%' THEN 'casper' ELSE NULL END)
    WHEN v.genotype_tg_style IS NOT NULL AND btrim(v.genotype_tg_style) <> ''
    THEN v.genotype_tg_style
    WHEN v.clutch_code LIKE 'LCL-%'
    THEN 'casper'
    ELSE NULL
  END AS marker_rollup_tg,

  CASE
    WHEN v.treated_clutch_code IS NOT NULL AND btrim(v.treated_clutch_code) <> ''
     AND v.treatment_code IS NOT NULL AND btrim(v.treatment_code) <> ''
     AND tt.treatment_basecodes_typed IS NOT NULL AND btrim(tt.treatment_basecodes_typed) <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || COALESCE(NULLIF(btrim(v.genotype_fluortag_style), ''), CASE WHEN v.clutch_code LIKE 'LCL-%' THEN 'casper' ELSE NULL END)
    WHEN v.genotype_fluortag_style IS NOT NULL AND btrim(v.genotype_fluortag_style) <> ''
    THEN v.genotype_fluortag_style
    WHEN v.clutch_code LIKE 'LCL-%'
    THEN 'casper'
    ELSE NULL
  END AS marker_rollup_fluortag,

  CASE
    WHEN v.treated_clutch_code IS NOT NULL AND btrim(v.treated_clutch_code) <> ''
     AND v.treatment_code IS NOT NULL AND btrim(v.treatment_code) <> ''
     AND tt.treatment_basecodes_typed IS NOT NULL AND btrim(tt.treatment_basecodes_typed) <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || COALESCE(NULLIF(btrim(v.genotype_fluororganelle_style), ''), CASE WHEN v.clutch_code LIKE 'LCL-%' THEN 'casper' ELSE NULL END)
    WHEN v.genotype_fluororganelle_style IS NOT NULL AND btrim(v.genotype_fluororganelle_style) <> ''
    THEN v.genotype_fluororganelle_style
    WHEN v.clutch_code LIKE 'LCL-%'
    THEN 'casper'
    ELSE NULL
  END AS marker_rollup_fluororganelle

FROM public.v_roi_overview v
LEFT JOIN treatment_tokens tt
  ON tt.treat_code = v.treatment_code;

COMMIT;
