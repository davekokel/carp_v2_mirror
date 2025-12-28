CREATE OR REPLACE VIEW public.v11_roi_treatment_table_display AS
WITH base AS (
  SELECT
    ps.experiment_date,
    ps.experiment_name,
    ps.plate_note,
    ps.slot_note,
    ps.slot_orientation,
    ra.id AS roi_id,
    ra.slot_id,
    ra.roi_code,
    ra.roi_index_within_slot,
    ra.roi_note_anatomy,
    ra.roi_path,
    ps.clutch_code,
    m.treated_clutch_id,
    tg.treated_clutch_code,
    ps.treat_code AS treatment_code,
    ps.treat_text AS treatment_text,
    NULLIF(btrim(tg.treatment_label_tg_style), '') AS tg_style,
    NULLIF(btrim(tg.treatment_label_fluortag_style), '') AS ft_style,
    NULLIF(btrim(tg.treatment_label_fluororganelle_style), '') AS fo_style,
    ra.v5_treatment_plasmid_base_codes AS v5_plasmids_raw,
    ra.v5_treatment_rna_base_codes AS v5_rnas_raw,
    NULL::text AS v5_dyes_raw
  FROM public.imaging_roi_annotations ra
  LEFT JOIN public.v11_imaging_plate_slot_overview ps
    ON ps.slot_id::uuid = ra.slot_id
  LEFT JOIN public.imaging_clutch_memberships m
    ON m.slot_id = ra.slot_id
  LEFT JOIN public.v11_treated_clutch_genotype_star_labels tg
    ON tg.treated_clutch_id = m.treated_clutch_id
),
clean AS (
  SELECT
    b.*,
    NULLIF(btrim(regexp_replace(COALESCE(b.tg_style, ''), '^.*>[[:space:]]*', '')), '') AS tg_label,
    NULLIF(btrim(regexp_replace(COALESCE(b.ft_style, ''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluortag_label,
    NULLIF(btrim(regexp_replace(COALESCE(b.fo_style, ''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluororganelle_label_raw,
    (regexp_match(COALESCE(b.treatment_text, ''), '(?i)(?:^|\\|)plasmids?=([^|]*)'))[1] AS plasmids_raw_from_text,
    (regexp_match(COALESCE(b.treatment_text, ''), '(?i)(?:^|\\|)rnas?=([^|]*)'))[1] AS rnas_raw_from_text,
    (regexp_match(COALESCE(b.treatment_text, ''), '(?i)(?:^|\\|)dyes?=([^|]*)'))[1] AS dyes_raw_from_text
  FROM base b
),
fmt AS (
  SELECT
    c.experiment_date,
    c.experiment_name,
    c.plate_note,
    c.slot_note,
    c.slot_orientation,
    c.roi_id,
    c.slot_id,
    c.roi_code,
    c.roi_index_within_slot,
    c.roi_note_anatomy,
    c.roi_path,
    c.clutch_code,
    c.treated_clutch_id,
    c.treated_clutch_code,
    c.treatment_code,
    c.treatment_text,
    c.tg_style,
    c.ft_style,
    c.fo_style,
    c.tg_label,
    c.fluortag_label,
    c.fluororganelle_label_raw,
    NULLIF(btrim(split_part(COALESCE(c.fluororganelle_label_raw, ''), '>', 1)), '') AS fluororganelle_name,
    NULLIF(btrim(split_part(COALESCE(c.fluororganelle_label_raw, ''), '>', 2)), '') AS fluororganelle_basecodes,

    NULLIF(btrim(COALESCE(c.plasmids_raw_from_text, c.v5_plasmids_raw, '')), '') AS plasmids_basecodes,
    NULLIF(btrim(COALESCE(c.rnas_raw_from_text, c.v5_rnas_raw, '')), '') AS rnas_basecodes,
    NULLIF(btrim(COALESCE(c.dyes_raw_from_text, c.v5_dyes_raw, '')), '') AS dyes_codes,

    CASE
      WHEN NULLIF(btrim(COALESCE(c.plasmids_raw_from_text, c.v5_plasmids_raw, '')), '') IS NULL THEN NULL::text
      ELSE
        ('plasmid(' ||
          regexp_replace(
            btrim(COALESCE(c.plasmids_raw_from_text, c.v5_plasmids_raw, '')),
            '\s*[;,]\s*|\s+',
            '), plasmid(',
            'g'
          )
        || ')')
    END AS plasmids_display,

    CASE
      WHEN NULLIF(btrim(COALESCE(c.rnas_raw_from_text, c.v5_rnas_raw, '')), '') IS NULL THEN NULL::text
      ELSE
        ('rna(' ||
          regexp_replace(
            btrim(COALESCE(c.rnas_raw_from_text, c.v5_rnas_raw, '')),
            '\s*[;,]\s*|\s+',
            '), rna(',
            'g'
          )
        || ')')
    END AS rnas_display,

    CASE
      WHEN NULLIF(btrim(COALESCE(c.dyes_raw_from_text, c.v5_dyes_raw, '')), '') IS NULL THEN NULL::text
      ELSE
        ('dye(' ||
          regexp_replace(
            btrim(COALESCE(c.dyes_raw_from_text, c.v5_dyes_raw, '')),
            '\s*[;,]\s*|\s+',
            '), dye(',
            'g'
          )
        || ')')
    END AS dyes_display

  FROM clean c
)
SELECT
  f.experiment_date,
  f.experiment_name,
  f.plate_note,
  f.slot_note,
  f.slot_orientation,
  f.roi_id,
  f.slot_id,
  f.roi_code,
  f.roi_index_within_slot,
  f.roi_note_anatomy,
  f.roi_path,
  f.clutch_code,
  f.treated_clutch_id,
  f.treated_clutch_code,
  f.treatment_code,
  f.treatment_text,
  f.tg_label,
  f.fluortag_label,
  f.fluororganelle_name,
  f.fluororganelle_basecodes,
  f.plasmids_basecodes,
  f.rnas_basecodes,
  f.dyes_codes,
  f.plasmids_display,
  f.rnas_display,
  f.dyes_display,
  NULL::text AS tx_gt_tg,
  NULL::text AS tx_gt_fluortag,
  NULL::text AS tx_gt_fluororganelle
FROM fmt f;
