BEGIN;

DROP VIEW IF EXISTS public.v11_roi_flat_table_display2;

CREATE VIEW public.v11_roi_flat_table_display2 AS
WITH one_treat AS (
  SELECT
    c.clutch_code,
    max(t.treat_text) AS treat_text
  FROM public.join_clutch_treatments j
  JOIN public.clutches c ON c.id = j.clutch_id
  JOIN public.treatments t ON t.id = j.treatment_id
  GROUP BY c.clutch_code
  HAVING count(*) = 1
)
SELECT
  r.experiment_date,
  r.experiment_name,
  r.plate_note,
  r.slot_note,
  r.slot_orientation,
  r.roi_id,
  ('roi-' || left(r.roi_id::text, 8)) AS roi_code,
  r.roi_code AS roi_label,
  r.roi_index_within_slot,
  r.roi_path,
  r.roi_note_anatomy,
  r.n_tiffs,
  r.clutch_code,
  r.treated_clutch_codes,
  r.treatment_codes,

  CASE
    WHEN ot.treat_text IS NOT NULL AND coalesce(btrim(r.tx_gt_tg),'') <> ''
      THEN ot.treat_text || ' > ' || r.tx_gt_tg
    ELSE coalesce(r.tx_gt_tg,'')
  END AS tx_gt_tg,

  CASE
    WHEN ot.treat_text IS NOT NULL AND coalesce(btrim(r.tx_gt_fluortag),'') <> ''
      THEN ot.treat_text || ' > ' || r.tx_gt_fluortag
    ELSE coalesce(r.tx_gt_fluortag,'')
  END AS tx_gt_fluortag,

  CASE
    WHEN ot.treat_text IS NOT NULL AND coalesce(btrim(r.tx_gt_fluororganelle),'') <> ''
      THEN ot.treat_text || ' > ' || r.tx_gt_fluororganelle
    ELSE coalesce(r.tx_gt_fluororganelle,'')
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
