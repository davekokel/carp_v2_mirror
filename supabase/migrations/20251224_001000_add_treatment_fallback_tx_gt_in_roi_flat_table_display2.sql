BEGIN;

DROP VIEW IF EXISTS public.v11_roi_flat_table_display2;

CREATE VIEW public.v11_roi_flat_table_display2 AS
WITH one_treat AS (
  SELECT
    c.clutch_code,
    max(t.treat_code) AS treat_code,
    max(t.treat_text) AS treat_text
  FROM public.join_clutch_treatments j
  JOIN public.clutches c ON c.id = j.clutch_id
  JOIN public.treatments t ON t.id = j.treatment_id
  GROUP BY c.clutch_code
  HAVING count(*) = 1
),
fallback AS (
  SELECT
    clutch_code,
    CASE
      WHEN treat_code LIKE 'T-LABEL-%' THEN treat_text
      ELSE treat_text
    END AS tx_fallback
  FROM one_treat
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

  COALESCE(NULLIF(btrim(r.tx_gt_tg),''), fb.tx_fallback, '') AS tx_gt_tg,
  COALESCE(NULLIF(btrim(r.tx_gt_fluortag),''), fb.tx_fallback, '') AS tx_gt_fluortag,
  COALESCE(NULLIF(btrim(r.tx_gt_fluororganelle),''), fb.tx_fallback, '') AS tx_gt_fluororganelle,

  r.plasmids_display,
  r.rnas_display,
  r.dyes_display,
  r.n_channels_total,
  r.n_channels_kept,
  r.kept_channels_key
FROM public.v11_roi_flat_table_display r
LEFT JOIN fallback fb
  ON fb.clutch_code = r.clutch_code;

COMMIT;
