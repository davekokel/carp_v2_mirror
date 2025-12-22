
DROP VIEW IF EXISTS public.v11_roi_flat_table_display;

CREATE VIEW public.v11_roi_flat_table_display AS
WITH base AS (
  SELECT
    ps.experiment_date,
    ps.experiment_name,
    ps.plate_note,
    ps.slot_note,
    ps.slot_orientation,
    ra.roi_code,
    ra.roi_index_within_slot,
    ra.roi_note_anatomy,
    ra.roi_path,
    ps.clutch_code,
    m.treated_clutch_id,
    tg.treated_clutch_code,
    ps.treat_code AS treatment_code,
    ps.treat_text AS treatment_text,
    NULLIF(btrim(tg.treatment_label_tg_style), '') AS tx_gt_tg,
    NULLIF(btrim(tg.treatment_label_fluortag_style), '') AS tx_gt_fluortag,
    NULLIF(btrim(tg.treatment_label_fluororganelle_style), '') AS tx_gt_fluororganelle
  FROM imaging_roi_annotations ra
  LEFT JOIN v11_imaging_plate_slot_overview ps
    ON ps.slot_id::uuid = ra.slot_id
  LEFT JOIN imaging_clutch_memberships m
    ON m.slot_id = ra.slot_id
  LEFT JOIN v11_treated_clutch_genotype_star_labels tg
    ON tg.treated_clutch_id = m.treated_clutch_id
),
clean AS (
  SELECT
    *,
    NULLIF(btrim(regexp_replace(tx_gt_tg, '^.*>[[:space:]]*', '')), '') AS tg_label,
    NULLIF(btrim(regexp_replace(tx_gt_fluortag, '^[[:space:]]*>[[:space:]]*', '')), '') AS fluortag_label,
    NULLIF(btrim(regexp_replace(tx_gt_fluororganelle, '^[[:space:]]*>[[:space:]]*', '')), '') AS fluororganelle_label_raw,
    (regexp_match(coalesce(treatment_text,''), '(?i)(?:^|\|)plasmids?=([^|]*)'))[1] AS plasmids_raw,
    (regexp_match(coalesce(treatment_text,''), '(?i)(?:^|\|)rnas?=([^|]*)'))[1] AS rnas_raw,
    (regexp_match(coalesce(treatment_text,''), '(?i)(?:^|\|)dyes?=([^|]*)'))[1] AS dyes_raw
  FROM base
),
fmt AS (
  SELECT
    roi_path,
    roi_note_anatomy,
    slot_orientation,
    plate_note,
    slot_note,
    experiment_name,
    experiment_date,
    roi_code,
    roi_index_within_slot,
    clutch_code,
    treated_clutch_code,
    treated_clutch_id,
    treatment_code,
    treatment_text,
    tx_gt_tg,
    tx_gt_fluortag,
    tx_gt_fluororganelle,
    tg_label,
    fluortag_label,
    split_part(fluororganelle_label_raw,'>',1) AS fluororganelle_name,
    split_part(fluororganelle_label_raw,'>',2) AS fluororganelle_basecodes,
    plasmids_raw,
    rnas_raw,
    dyes_raw
  FROM clean
)
SELECT * FROM fmt;
