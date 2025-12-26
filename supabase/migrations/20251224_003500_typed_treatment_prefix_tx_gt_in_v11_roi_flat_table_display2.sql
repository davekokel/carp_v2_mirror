BEGIN;

DROP VIEW IF EXISTS public.v11_roi_flat_table_display2;

CREATE VIEW public.v11_roi_flat_table_display2 AS
WITH jct1 AS (
  SELECT c.clutch_code, count(*) AS n_join
  FROM public.join_clutch_treatments j
  JOIN public.clutches c ON c.id = j.clutch_id
  GROUP BY 1
),
one_jct AS (
  SELECT c.clutch_code, j.treatment_id
  FROM public.join_clutch_treatments j
  JOIN public.clutches c ON c.id = j.clutch_id
  JOIN jct1 n ON n.clutch_code = c.clutch_code AND n.n_join = 1
),
treat_parts AS (
  SELECT
    oj.clutch_code,
    lower(coalesce(tmc.delivery_form,'')) AS delivery_form,
    upper(coalesce(cons.base_code,''))    AS base_code
  FROM one_jct oj
  JOIN public.treatment_mixes tm
    ON tm.treatment_id = oj.treatment_id
  JOIN public.treatment_mix_constructs tmc
    ON tmc.mix_id = tm.id
  JOIN public.constructs cons
    ON cons.id = tmc.construct_id
  WHERE coalesce(btrim(cons.base_code),'') <> ''
),
treat_typed AS (
  SELECT
    clutch_code,
    string_agg(
      DISTINCT (delivery_form || '(' || base_code || ')'),
      '|'
      ORDER BY (delivery_form || '(' || base_code || ')')
    ) AS treat_basecodes_typed
  FROM treat_parts
  WHERE delivery_form IN ('plasmid','rna','crispr')
  GROUP BY 1
),
one_treat AS (
  SELECT clutch_code, treat_basecodes_typed
  FROM treat_typed
)
SELECT
  r.experiment_date,
  r.experiment_name,
  r.plate_note,
  r.slot_note,
  r.slot_orientation,
  r.roi_id,
  r.roi_code,
  r.roi_index_within_slot,
  r.roi_note_anatomy,
  r.roi_path,
  r.n_tiffs,
  r.clutch_code,
  r.treated_clutch_codes,
  r.treatment_codes,

  CASE
    WHEN coalesce(btrim(ot.treat_basecodes_typed),'') <> '' AND coalesce(btrim(r.tx_gt_tg),'') <> ''
      THEN ot.treat_basecodes_typed || ' > ' || r.tx_gt_tg
    WHEN coalesce(btrim(ot.treat_basecodes_typed),'') <> '' AND coalesce(btrim(r.tx_gt_tg),'') = ''
      THEN ot.treat_basecodes_typed || CASE WHEN coalesce(btrim(c.genetic_background),'') <> '' THEN ' > ' || c.genetic_background ELSE '' END
    ELSE coalesce(r.tx_gt_tg,'')
  END AS tx_gt_tg,

  CASE
    WHEN coalesce(btrim(ot.treat_basecodes_typed),'') <> '' AND coalesce(btrim(r.tx_gt_fluortag),'') <> ''
      THEN ot.treat_basecodes_typed || ' > ' || r.tx_gt_fluortag
    WHEN coalesce(btrim(ot.treat_basecodes_typed),'') <> '' AND coalesce(btrim(r.tx_gt_fluortag),'') = ''
      THEN ot.treat_basecodes_typed || CASE WHEN coalesce(btrim(c.genetic_background),'') <> '' THEN ' > ' || c.genetic_background ELSE '' END
    ELSE coalesce(r.tx_gt_fluortag,'')
  END AS tx_gt_fluortag,

  CASE
    WHEN coalesce(btrim(ot.treat_basecodes_typed),'') <> '' AND coalesce(btrim(r.tx_gt_fluororganelle),'') <> ''
      THEN ot.treat_basecodes_typed || ' > ' || r.tx_gt_fluororganelle
    WHEN coalesce(btrim(ot.treat_basecodes_typed),'') <> '' AND coalesce(btrim(r.tx_gt_fluororganelle),'') = ''
      THEN ot.treat_basecodes_typed || CASE WHEN coalesce(btrim(c.genetic_background),'') <> '' THEN ' > ' || c.genetic_background ELSE '' END
    ELSE coalesce(r.tx_gt_fluororganelle,'')
  END AS tx_gt_fluororganelle,

  r.plasmids_display,
  r.rnas_display,
  r.dyes_display,
  r.n_channels_total,
  r.n_channels_kept,
  r.kept_channels_key
FROM public.v11_roi_flat_table_display r
LEFT JOIN public.clutches c
  ON c.clutch_code = r.clutch_code
LEFT JOIN one_treat ot
  ON ot.clutch_code = r.clutch_code;

COMMIT;
