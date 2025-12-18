BEGIN;

WITH legacy_mixes AS (
  SELECT tm.id AS mix_id
  FROM public.treatments t
  JOIN public.treatment_mixes tm ON tm.treatment_id = t.id
  WHERE t.treat_code LIKE 'T-LEGACY-%'
)
UPDATE public.treatment_mix_constructs tmc
SET delivery_form = CASE
  WHEN c.construct_kind = 'plasmid' THEN 'plasmid'
  WHEN c.construct_kind = 'rna' THEN 'rna'
  WHEN c.construct_kind = 'crispr' THEN 'crispr'
  ELSE tmc.delivery_form
END
FROM public.constructs c
WHERE tmc.construct_id = c.id
  AND tmc.mix_id IN (SELECT mix_id FROM legacy_mixes)
  AND (tmc.delivery_form IS NULL OR btrim(tmc.delivery_form) = '')
  AND c.construct_kind IN ('plasmid','rna','crispr');

WITH legacy_mixes AS (
  SELECT tm.id AS mix_id
  FROM public.treatments t
  JOIN public.treatment_mixes tm ON tm.treatment_id = t.id
  WHERE t.treat_code LIKE 'T-LEGACY-%'
),
ranked AS (
  SELECT
    tmc.id,
    row_number() OVER (
      PARTITION BY
        tmc.mix_id,
        tmc.construct_id,
        COALESCE(tmc.delivery_form,''),
        COALESCE(tmc.amount_pg::text,''),
        COALESCE(tmc.units,''),
        COALESCE(tmc.role,''),
        COALESCE(tmc.notes,''),
        COALESCE(tmc.concentration,'')
      ORDER BY tmc.created_at ASC, tmc.id ASC
    ) AS rn
  FROM public.treatment_mix_constructs tmc
  WHERE tmc.mix_id IN (SELECT mix_id FROM legacy_mixes)
)
DELETE FROM public.treatment_mix_constructs tmc
USING ranked r
WHERE tmc.id = r.id
  AND r.rn > 1;

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
    THEN tt.treatment_basecodes_typed || ' > ' || COALESCE(
      NULLIF(btrim(v.genotype_basecodes), ''),
      CASE WHEN v.clutch_code LIKE 'LCL-%' THEN 'casper' ELSE NULL END
    )
    WHEN v.genotype_basecodes IS NOT NULL AND btrim(v.genotype_basecodes) <> ''
    THEN v.genotype_basecodes
    WHEN v.clutch_code LIKE 'LCL-%' THEN 'casper'
    ELSE NULL
  END AS marker_rollup_tg,

  CASE
    WHEN v.treated_clutch_code IS NOT NULL AND btrim(v.treated_clutch_code) <> ''
     AND v.treatment_code IS NOT NULL AND btrim(v.treatment_code) <> ''
     AND tt.treatment_basecodes_typed IS NOT NULL AND btrim(tt.treatment_basecodes_typed) <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || COALESCE(
      NULLIF(btrim(v.genotype_fluortag_style), ''),
      CASE WHEN v.clutch_code LIKE 'LCL-%' THEN 'casper' ELSE NULL END
    )
    WHEN v.genotype_fluortag_style IS NOT NULL AND btrim(v.genotype_fluortag_style) <> ''
    THEN v.genotype_fluortag_style
    WHEN v.clutch_code LIKE 'LCL-%' THEN 'casper'
    ELSE NULL
  END AS marker_rollup_fluortag,

  CASE
    WHEN v.treated_clutch_code IS NOT NULL AND btrim(v.treated_clutch_code) <> ''
     AND v.treatment_code IS NOT NULL AND btrim(v.treatment_code) <> ''
     AND tt.treatment_basecodes_typed IS NOT NULL AND btrim(tt.treatment_basecodes_typed) <> ''
    THEN tt.treatment_basecodes_typed || ' > ' || COALESCE(
      NULLIF(btrim(v.genotype_fluororganelle_style), ''),
      CASE WHEN v.clutch_code LIKE 'LCL-%' THEN 'casper' ELSE NULL END
    )
    WHEN v.genotype_fluororganelle_style IS NOT NULL AND btrim(v.genotype_fluororganelle_style) <> ''
    THEN v.genotype_fluororganelle_style
    WHEN v.clutch_code LIKE 'LCL-%' THEN 'casper'
    ELSE NULL
  END AS marker_rollup_fluororganelle

FROM public.v_roi_overview v
LEFT JOIN treatment_tokens tt
  ON tt.treat_code = v.treatment_code;

COMMIT;
