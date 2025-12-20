-- PURPOSE
--   Canonicalize ROI rollups so treated ROIs always have a stable RHS “genotype_display”.
--
-- DESIGN
--   genotype_display precedence (highest → lowest):
--     1) v_roi_overview.genotype_tg_style
--     2) v_roi_overview.genotype_pretty
--     3) v_roi_overview.genotype_basecodes
--     4) clutches.genetic_background
--
--   marker_rollup_tg (treated):
--     <treatment_tokens_typed> > <genotype_display>
--
--   This prevents “invented transgenes” when genotype basecodes are missing: background is the fallback.
--   It is expected that some treated ROIs have RHS=casper when no transgenes are available.
--
-- NOTES
--   This migration only rewrites VIEW DEFINITIONS; no data backfill. Loader(s) must populate clutches.genetic_background.
--

BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview_rollups_qc;
DROP VIEW IF EXISTS public.v_roi_overview_rollups;

CREATE VIEW public.v_roi_overview_rollups AS
WITH treatment_tokens AS (
  SELECT
    t.treat_code,
    (
      SELECT string_agg(s.tok, '; ' ORDER BY s.tok)
      FROM (
        SELECT DISTINCT (tmc.delivery_form || '(' || lower(c.base_code) || ')') AS tok
        FROM public.treatment_mixes tm
        JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
        JOIN public.constructs c ON c.id = tmc.construct_id
        WHERE tm.treatment_id = t.id
      ) s
      WHERE s.tok IS NOT NULL AND btrim(s.tok) <> ''
    ) AS treatment_basecodes_typed
  FROM public.treatments t
),
geno_display AS (
  SELECT
    v.roi_id,
    COALESCE(
      NULLIF(btrim(v.genotype_tg_style), ''),
      NULLIF(btrim(v.genotype_pretty), ''),
      NULLIF(btrim(v.genotype_basecodes), ''),
      NULLIF(btrim(cl.genetic_background), '')
    ) AS genotype_display,
    NULLIF(btrim(v.genotype_fluortag_style), '') AS geno_fluortag,
    NULLIF(btrim(v.genotype_fluororganelle_style), '') AS geno_fluororganelle
  FROM public.v_roi_overview v
  LEFT JOIN public.clutches cl ON cl.clutch_code = v.clutch_code
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
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
     AND COALESCE(btrim(gd.genotype_display),'') <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || gd.genotype_display
    WHEN COALESCE(btrim(gd.genotype_display),'') <> '' THEN gd.genotype_display
    ELSE NULL
  END AS marker_rollup_tg,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
     AND gd.geno_fluortag IS NOT NULL AND btrim(gd.geno_fluortag) <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || gd.geno_fluortag
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
    THEN tt.treatment_basecodes_typed
    ELSE gd.geno_fluortag
  END AS marker_rollup_fluortag,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
     AND gd.geno_fluororganelle IS NOT NULL AND btrim(gd.geno_fluororganelle) <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || gd.geno_fluororganelle
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
    THEN tt.treatment_basecodes_typed
    ELSE gd.geno_fluororganelle
  END AS marker_rollup_fluororganelle,

  gd.genotype_display,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
     AND COALESCE(btrim(gd.genotype_display),'') <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || gd.genotype_display
    WHEN COALESCE(btrim(gd.genotype_display),'') <> '' THEN gd.genotype_display
    ELSE NULL
  END AS marker_rollup_display_tg,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
     AND gd.geno_fluortag IS NOT NULL AND btrim(gd.geno_fluortag) <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || gd.geno_fluortag
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
    THEN tt.treatment_basecodes_typed
    ELSE gd.geno_fluortag
  END AS marker_rollup_display_fluortag,

  CASE
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
     AND gd.geno_fluororganelle IS NOT NULL AND btrim(gd.geno_fluororganelle) <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || gd.geno_fluororganelle
    WHEN COALESCE(btrim(v.treated_clutch_code),'') <> ''
     AND COALESCE(btrim(v.treatment_code),'') <> ''
     AND COALESCE(btrim(tt.treatment_basecodes_typed),'') <> ''
    THEN tt.treatment_basecodes_typed
    ELSE gd.geno_fluororganelle
  END AS marker_rollup_display_fluororganelle

FROM public.v_roi_overview v
LEFT JOIN treatment_tokens tt ON tt.treat_code = v.treatment_code
LEFT JOIN geno_display gd ON gd.roi_id = v.roi_id
;

CREATE VIEW public.v_roi_overview_rollups_qc AS
WITH v AS (SELECT * FROM public.v_roi_overview_rollups),
treated AS (
  SELECT * FROM v
  WHERE COALESCE(btrim(treated_clutch_code),'') <> ''
)
SELECT
  (SELECT count(*) FROM v) AS n_rows,
  (SELECT count(*) FROM treated) AS n_treated_rows,
  (SELECT count(*) FROM treated WHERE COALESCE(btrim(marker_rollup_display_tg),'') = '') AS n_treated_missing_display_tg
;

COMMIT;
