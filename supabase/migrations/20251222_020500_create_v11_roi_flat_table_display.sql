CREATE OR REPLACE VIEW public.v11_roi_flat_table_display AS
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
    NULLIF(btrim(tg.treatment_label_tg_style), '') AS tg_style,
    NULLIF(btrim(tg.treatment_label_fluortag_style), '') AS ft_style,
    NULLIF(btrim(tg.treatment_label_fluororganelle_style), '') AS fo_style
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
    *,
    NULLIF(btrim(regexp_replace(coalesce(tg_style,''), '^.*>[[:space:]]*', '')), '') AS tg_label,
    NULLIF(btrim(regexp_replace(coalesce(ft_style,''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluortag_label,
    NULLIF(btrim(regexp_replace(coalesce(fo_style,''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluororganelle_label_raw,

    (regexp_match(coalesce(treatment_text,''), '(?i)(?:^|\|)plasmids?=([^|]*)'))[1] AS plasmids_raw,
    (regexp_match(coalesce(treatment_text,''), '(?i)(?:^|\|)rnas?=([^|]*)'))[1]     AS rnas_raw,
    (regexp_match(coalesce(treatment_text,''), '(?i)(?:^|\|)dyes?=([^|]*)'))[1]     AS dyes_raw
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

    tg_label,
    fluortag_label,

    NULLIF(btrim(split_part(coalesce(fluororganelle_label_raw,''), '>', 1)), '') AS fluororganelle_name,
    NULLIF(btrim(split_part(coalesce(fluororganelle_label_raw,''), '>', 2)), '') AS fluororganelle_basecodes,

    NULLIF(btrim(plasmids_raw), '') AS plasmids_basecodes,
    NULLIF(btrim(rnas_raw), '')     AS rnas_basecodes,
    NULLIF(btrim(dyes_raw), '')     AS dyes_codes,

    CASE
      WHEN NULLIF(btrim(plasmids_raw), '') IS NULL THEN NULL
      ELSE 'plasmid(' || regexp_replace(btrim(plasmids_raw), '\s*[;,]\s*|\s+', '), plasmid(', 'g') || ')'
    END AS plasmids_display,

    CASE
      WHEN NULLIF(btrim(rnas_raw), '') IS NULL THEN NULL
      ELSE 'rna(' || regexp_replace(btrim(rnas_raw), '\s*[;,]\s*|\s+', '), rna(', 'g') || ')'
    END AS rnas_display,

    CASE
      WHEN NULLIF(btrim(dyes_raw), '') IS NULL THEN NULL
      ELSE 'dye(' || regexp_replace(btrim(dyes_raw), '\s*[;,]\s*|\s+', '), dye(', 'g') || ')'
    END AS dyes_display
  FROM clean
)
SELECT * FROM fmt;
