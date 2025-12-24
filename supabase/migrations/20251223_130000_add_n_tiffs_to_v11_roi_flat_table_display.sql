BEGIN;

DROP VIEW IF EXISTS public.v11_roi_flat_table_display;

CREATE VIEW public.v11_roi_flat_table_display AS
SELECT
  t.experiment_date,
  t.experiment_name,
  t.plate_note,
  t.slot_note,
  t.slot_orientation,
  t.roi_id,
  t.roi_code,
  t.roi_index_within_slot,
  t.roi_note_anatomy,
  t.roi_path,
  ira.n_tiffs,
  t.clutch_code,
  count(DISTINCT t.treated_clutch_id) FILTER (WHERE t.treated_clutch_id IS NOT NULL) AS n_treated_clutches,
  string_agg(DISTINCT t.treated_clutch_code, '; ' ORDER BY t.treated_clutch_code) FILTER (WHERE t.treated_clutch_code IS NOT NULL) AS treated_clutch_codes,
  string_agg(DISTINCT t.treatment_code, '; ' ORDER BY t.treatment_code) FILTER (WHERE t.treatment_code IS NOT NULL) AS treatment_codes,
  string_agg(DISTINCT t.plasmids_display, '; ' ORDER BY t.plasmids_display) FILTER (WHERE t.plasmids_display IS NOT NULL) AS plasmids_display,
  string_agg(DISTINCT t.rnas_display, '; ' ORDER BY t.rnas_display) FILTER (WHERE t.rnas_display IS NOT NULL) AS rnas_display,
  string_agg(DISTINCT t.dyes_display, '; ' ORDER BY t.dyes_display) FILTER (WHERE t.dyes_display IS NOT NULL) AS dyes_display,
  string_agg(DISTINCT t.tx_gt_tg, '; ' ORDER BY t.tx_gt_tg) FILTER (WHERE t.tx_gt_tg IS NOT NULL) AS tx_gt_tg,
  string_agg(DISTINCT t.tx_gt_fluortag, '; ' ORDER BY t.tx_gt_fluortag) FILTER (WHERE t.tx_gt_fluortag IS NOT NULL) AS tx_gt_fluortag,
  string_agg(DISTINCT t.tx_gt_fluororganelle, '; ' ORDER BY t.tx_gt_fluororganelle) FILTER (WHERE t.tx_gt_fluororganelle IS NOT NULL) AS tx_gt_fluororganelle,
  ch.n_channels_total,
  ch.n_channels_kept,
  ch.kept_channels_key
FROM public.v11_roi_treatment_table_display t
LEFT JOIN public.imaging_roi_annotations ira
  ON ira.id = t.roi_id
LEFT JOIN public.v_imaging_roi_channel_qc_rollup_v2 ch
  ON ch.roi_id = t.roi_id
GROUP BY
  t.experiment_date,
  t.experiment_name,
  t.plate_note,
  t.slot_note,
  t.slot_orientation,
  t.roi_id,
  t.roi_code,
  t.roi_index_within_slot,
  t.roi_note_anatomy,
  t.roi_path,
  ira.n_tiffs,
  t.clutch_code,
  ch.n_channels_total,
  ch.n_channels_kept,
  ch.kept_channels_key;

COMMIT;
