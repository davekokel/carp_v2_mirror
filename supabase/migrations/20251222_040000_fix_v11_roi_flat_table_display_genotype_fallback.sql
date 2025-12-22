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
    b.*,
    NULLIF(btrim(regexp_replace(COALESCE(b.tg_style, ''), '^.*>[[:space:]]*', '')), '') AS tg_label,
    NULLIF(btrim(regexp_replace(COALESCE(b.ft_style, ''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluortag_label,
    NULLIF(btrim(regexp_replace(COALESCE(b.fo_style, ''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluororganelle_label_raw,
    (regexp_match(COALESCE(b.treatment_text, ''), '(?i)(?:^|\\|)plasmids?=([^|]*)'))[1] AS plasmids_raw,
    (regexp_match(COALESCE(b.treatment_text, ''), '(?i)(?:^|\\|)rnas?=([^|]*)'))[1] AS rnas_raw,
    (regexp_match(COALESCE(b.treatment_text, ''), '(?i)(?:^|\\|)dyes?=([^|]*)'))[1] AS dyes_raw
  FROM base b
),
fmt AS (
  SELECT
    c.experiment_date,
    c.experiment_name,
    c.plate_note,
    c.slot_note,
    c.slot_orientation,
    c.roi_code,
    c.roi_index_within_slot,
    c.roi_note_anatomy,
    c.roi_path,
    c.clutch_code,
    c.treated_clutch_id,
    c.treated_clutch_code,
    c.treatment_code,
    c.treatment_text,
    c.tg_label,
    c.fluortag_label,
    NULLIF(btrim(split_part(COALESCE(c.fluororganelle_label_raw, ''), '>', 1)), '') AS fluororganelle_name,
    NULLIF(btrim(split_part(COALESCE(c.fluororganelle_label_raw, ''), '>', 2)), '') AS fluororganelle_basecodes,
    NULLIF(btrim(c.plasmids_raw), '') AS plasmids_basecodes,
    NULLIF(btrim(c.rnas_raw), '') AS rnas_basecodes,
    NULLIF(btrim(c.dyes_raw), '') AS dyes_codes,
    CASE
      WHEN NULLIF(btrim(c.plasmids_raw), '') IS NULL THEN NULL
      ELSE ('plasmid(' || regexp_replace(btrim(c.plasmids_raw), '\s*[;,]\s*|\s+', '), plasmid(', 'g') || ')')
    END AS plasmids_display,
    CASE
      WHEN NULLIF(btrim(c.rnas_raw), '') IS NULL THEN NULL
      ELSE ('rna(' || regexp_replace(btrim(c.rnas_raw), '\s*[;,]\s*|\s+', '), rna(', 'g') || ')')
    END AS rnas_display,
    CASE
      WHEN NULLIF(btrim(c.dyes_raw), '') IS NULL THEN NULL
      ELSE ('dye(' || regexp_replace(btrim(c.dyes_raw), '\s*[;,]\s*|\s+', '), dye(', 'g') || ')')
    END AS dyes_display
  FROM clean c
),
labels AS (
  SELECT
    f.roi_code,
    tls.treatment_display,
    gv.genotype_pretty,
    gls.fluor_tag_style AS gt_fluortag,
    gls.fluor_organelle_style AS gt_organelle,
    CASE
      WHEN NULLIF(btrim(COALESCE(tls.treatment_display, '')), '') IS NOT NULL
           AND NULLIF(btrim(COALESCE(gv.genotype_pretty, '')), '') IS NOT NULL
        THEN (tls.treatment_display || ' > ' || gv.genotype_pretty)
      WHEN NULLIF(btrim(COALESCE(tls.treatment_display, '')), '') IS NOT NULL
        THEN tls.treatment_display
      WHEN NULLIF(btrim(COALESCE(gv.genotype_pretty, '')), '') IS NOT NULL
        THEN gv.genotype_pretty
      ELSE NULL
    END AS tx_gt_tg,
    CASE
      WHEN NULLIF(btrim(COALESCE(tls.fluor_tag_style, '')), '') IS NULL THEN NULL
      WHEN tls.treatment_display ILIKE 'rna(%' AND tls.treatment_display NOT ILIKE '%plasmid(%' THEN ('rna(' || tls.fluor_tag_style || ')')
      WHEN tls.treatment_display ILIKE 'plasmid(%' AND tls.treatment_display NOT ILIKE '%rna(%' THEN ('plasmid(' || tls.fluor_tag_style || ')')
      ELSE tls.fluor_tag_style
    END AS treat_fluortag_disp,
    CASE
      WHEN NULLIF(btrim(COALESCE(tls.fluor_organelle_style, '')), '') IS NULL THEN NULL
      WHEN tls.treatment_display ILIKE 'rna(%' AND tls.treatment_display NOT ILIKE '%plasmid(%' THEN ('rna(' || tls.fluor_organelle_style || ')')
      WHEN tls.treatment_display ILIKE 'plasmid(%' AND tls.treatment_display NOT ILIKE '%rna(%' THEN ('plasmid(' || tls.fluor_organelle_style || ')')
      ELSE tls.fluor_organelle_style
    END AS treat_organelle_disp
  FROM fmt f
  LEFT JOIN public.clutches c ON c.clutch_code = f.clutch_code
  LEFT JOIN public.genotypes_v11 gv ON gv.id = c.genotype_v11_id
  LEFT JOIN public.v11_genotype_label_star gls ON gls.genotype_v11_id = c.genotype_v11_id
  LEFT JOIN public.treated_clutches_v11 tc ON tc.treated_clutch_code = f.treated_clutch_code
  LEFT JOIN public.v11_treatment_label_star tls ON tls.treatment_id::uuid = tc.treatment_id
)
SELECT
  f.*,
  l.tx_gt_tg,
  CASE
    WHEN NULLIF(btrim(COALESCE(l.treat_fluortag_disp, '')), '') IS NOT NULL
         AND NULLIF(btrim(COALESCE(l.gt_fluortag, '')), '') IS NOT NULL
      THEN (l.treat_fluortag_disp || ' > ' || l.gt_fluortag)
    WHEN NULLIF(btrim(COALESCE(l.treat_fluortag_disp, '')), '') IS NOT NULL
      THEN l.treat_fluortag_disp
    WHEN NULLIF(btrim(COALESCE(l.gt_fluortag, '')), '') IS NOT NULL
      THEN l.gt_fluortag
    WHEN NULLIF(btrim(COALESCE(f.fluortag_label, '')), '') IS NOT NULL
      THEN f.fluortag_label
    ELSE NULL
  END AS tx_gt_fluortag,
  CASE
    WHEN NULLIF(btrim(COALESCE(l.treat_organelle_disp, '')), '') IS NOT NULL
         AND NULLIF(btrim(COALESCE(l.gt_organelle, '')), '') IS NOT NULL
      THEN (l.treat_organelle_disp || ' > ' || l.gt_organelle)
    WHEN NULLIF(btrim(COALESCE(l.treat_organelle_disp, '')), '') IS NOT NULL
      THEN l.treat_organelle_disp
    WHEN NULLIF(btrim(COALESCE(l.gt_organelle, '')), '') IS NOT NULL
      THEN l.gt_organelle
    WHEN NULLIF(btrim(COALESCE(f.fluororganelle_name, '')), '') IS NOT NULL
         AND NULLIF(btrim(COALESCE(f.fluororganelle_basecodes, '')), '') IS NOT NULL
      THEN (f.fluororganelle_name || ' > ' || f.fluororganelle_basecodes)
    WHEN NULLIF(btrim(COALESCE(f.fluororganelle_name, '')), '') IS NOT NULL
      THEN f.fluororganelle_name
    ELSE NULL
  END AS tx_gt_fluororganelle
FROM fmt f
LEFT JOIN labels l ON l.roi_code = f.roi_code;
