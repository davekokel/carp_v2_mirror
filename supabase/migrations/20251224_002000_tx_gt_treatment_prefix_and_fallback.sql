BEGIN;

DROP VIEW IF EXISTS public.v11_roi_flat_table_display2;

CREATE VIEW public.v11_roi_flat_table_display2 AS
WITH jct1 AS (
  SELECT
    c.clutch_code,
    count(*) AS n_join
  FROM public.join_clutch_treatments j
  JOIN public.clutches c ON c.id = j.clutch_id
  GROUP BY 1
),
one_treat AS (
  SELECT
    c.clutch_code,
    coalesce(nullif(btrim(t.treat_text),''), t.treat_code) AS treat_prefix
  FROM public.join_clutch_treatments j
  JOIN public.clutches c ON c.id = j.clutch_id
  JOIN public.treatments t ON t.id = j.treatment_id
  JOIN jct1 n ON n.clutch_code = c.clutch_code AND n.n_join = 1
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
    WHEN ot.treat_prefix IS NOT NULL AND coalesce(btrim(r.tx_gt_tg),'') <> ''
      THEN ot.treat_prefix || ' > ' || r.tx_gt_tg
    ELSE coalesce(nullif(btrim(r.tx_gt_tg),''), ot.treat_prefix, '')
  END AS tx_gt_tg,

  CASE
    WHEN ot.treat_prefix IS NOT NULL AND coalesce(btrim(r.tx_gt_fluortag),'') <> ''
      THEN ot.treat_prefix || ' > ' || r.tx_gt_fluortag
    ELSE coalesce(nullif(btrim(r.tx_gt_fluortag),''), ot.treat_prefix, '')
  END AS tx_gt_fluortag,

  CASE
    WHEN ot.treat_prefix IS NOT NULL AND coalesce(btrim(r.tx_gt_fluororganelle),'') <> ''
      THEN ot.treat_prefix || ' > ' || r.tx_gt_fluororganelle
    ELSE coalesce(nullif(btrim(r.tx_gt_fluororganelle),''), ot.treat_prefix, '')
  END AS tx_gt_fluororganelle,

  r.plasmids_display,
  r.rnas_display,
  r.dyes_display,
  r.n_channels_total,
  r.n_channels_kept,
  r.kept_channels_key
FROM public.v11_roi_flat_table_display r
LEFT JOIN one_treat ot
  ON ot.clutch_code = r.clutch_code;

COMMIT;
