BEGIN;

-- 1) Preserve current ROI×treatment behavior under a new name, with stable ROI identity.
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
    NULLIF(btrim(regexp_replace(COALESCE(b.tg_style,''), '^.*>[[:space:]]*', '')), '') AS tg_label,
    NULLIF(btrim(regexp_replace(COALESCE(b.ft_style,''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluortag_label,
    NULLIF(btrim(regexp_replace(COALESCE(b.fo_style,''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluororganelle_label_raw,
    (regexp_match(COALESCE(b.treatment_text,''), '(?i)(?:^|\\|)plasmids?=([^|]*)'))[1] AS plasmids_raw,
    (regexp_match(COALESCE(b.treatment_text,''), '(?i)(?:^|\\|)rnas?=([^|]*)'))[1]     AS rnas_raw,
    (regexp_match(COALESCE(b.treatment_text,''), '(?i)(?:^|\\|)dyes?=([^|]*)'))[1]     AS dyes_raw
  FROM base b
),
fmt AS (
  SELECT
    c.*,
    NULLIF(btrim(split_part(COALESCE(c.fluororganelle_label_raw,''), '>', 1)), '') AS fluororganelle_name,
    NULLIF(btrim(split_part(COALESCE(c.fluororganelle_label_raw,''), '>', 2)), '') AS fluororganelle_basecodes,
    NULLIF(btrim(c.plasmids_raw), '') AS plasmids_basecodes,
    NULLIF(btrim(c.rnas_raw), '')     AS rnas_basecodes,
    NULLIF(btrim(c.dyes_raw), '')     AS dyes_codes,
    CASE
      WHEN NULLIF(btrim(c.plasmids_raw), '') IS NULL THEN NULL
      ELSE 'plasmid(' || regexp_replace(btrim(c.plasmids_raw), '\s*[;,]\s*|\s+', '), plasmid(', 'g') || ')'
    END AS plasmids_display,
    CASE
      WHEN NULLIF(btrim(c.rnas_raw), '') IS NULL THEN NULL
      ELSE 'rna(' || regexp_replace(btrim(c.rnas_raw), '\s*[;,]\s*|\s+', '), rna(', 'g') || ')'
    END AS rnas_display,
    CASE
      WHEN NULLIF(btrim(c.dyes_raw), '') IS NULL THEN NULL
      ELSE 'dye(' || regexp_replace(btrim(c.dyes_raw), '\s*[;,]\s*|\s+', '), dye(', 'g') || ')'
    END AS dyes_display
  FROM clean c
),
labels AS (
  SELECT
    f.roi_id,
    f.roi_code,
    f.roi_path,
    tls.treatment_display,
    gv.genotype_pretty,
    gls.fluor_tag_style       AS gt_fluortag,
    gls.fluor_organelle_style AS gt_organelle,
    CASE
      WHEN NULLIF(btrim(COALESCE(tls.treatment_display,'')), '') IS NOT NULL
       AND NULLIF(btrim(COALESCE(gv.genotype_pretty,'')), '') IS NOT NULL
        THEN tls.treatment_display || ' > ' || gv.genotype_pretty
      WHEN NULLIF(btrim(COALESCE(tls.treatment_display,'')), '') IS NOT NULL
        THEN tls.treatment_display
      WHEN NULLIF(btrim(COALESCE(gv.genotype_pretty,'')), '') IS NOT NULL
        THEN gv.genotype_pretty
      ELSE NULL
    END AS tx_gt_tg,
    CASE
      WHEN NULLIF(btrim(COALESCE(tls.fluor_tag_style,'')), '') IS NULL THEN NULL
      WHEN tls.treatment_display ~~* 'rna(%' AND tls.treatment_display !~~* '%plasmid(%'
        THEN 'rna(' || tls.fluor_tag_style || ')'
      WHEN tls.treatment_display ~~* 'plasmid(%' AND tls.treatment_display !~~* '%rna(%'
        THEN 'plasmid(' || tls.fluor_tag_style || ')'
      ELSE tls.fluor_tag_style
    END AS treat_fluortag_disp,
    CASE
      WHEN NULLIF(btrim(COALESCE(tls.fluor_organelle_style,'')), '') IS NULL THEN NULL
      WHEN tls.treatment_display ~~* 'rna(%' AND tls.treatment_display !~~* '%plasmid(%'
        THEN 'rna(' || tls.fluor_organelle_style || ')'
      WHEN tls.treatment_display ~~* 'plasmid(%' AND tls.treatment_display !~~* '%rna(%'
        THEN 'plasmid(' || tls.fluor_organelle_style || ')'
      ELSE tls.fluor_organelle_style
    END AS treat_organelle_disp
  FROM fmt f
  LEFT JOIN public.clutches c
    ON c.clutch_code = f.clutch_code
  LEFT JOIN public.genotypes_v11 gv
    ON gv.id = c.genotype_v11_id
  LEFT JOIN public.v11_genotype_label_star gls
    ON gls.genotype_v11_id = c.genotype_v11_id
  LEFT JOIN public.treated_clutches_v11 tc
    ON tc.treated_clutch_code = f.treated_clutch_code
  LEFT JOIN public.v11_treatment_label_star tls
    ON tls.treatment_id::uuid = tc.treatment_id
),
labels2 AS (
  SELECT
    roi_id,
    tx_gt_tg,
    NULLIF(btrim(COALESCE(treat_fluortag_disp,'')), '') AS treat_fluortag_norm,
    NULLIF(btrim(COALESCE(gt_fluortag,'')), '')         AS gt_fluortag_norm,
    NULLIF(btrim(COALESCE(treat_organelle_disp,'')), '') AS treat_organelle_norm,
    NULLIF(btrim(COALESCE(gt_organelle,'')), '')         AS gt_organelle_norm
  FROM labels
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
  l2.tx_gt_tg,
  CASE
    WHEN COALESCE(NULLIF(btrim(COALESCE(l2.treat_fluortag_norm,'')), ''), NULL) IS NULL
     AND COALESCE(NULLIF(btrim(COALESCE(l2.gt_fluortag_norm,'')), ''), NULL) IS NULL
      THEN NULL
    WHEN COALESCE(NULLIF(btrim(COALESCE(l2.treat_fluortag_norm,'')), ''), NULL) IS NULL
      THEN l2.gt_fluortag_norm
    WHEN COALESCE(NULLIF(btrim(COALESCE(l2.gt_fluortag_norm,'')), ''), NULL) IS NULL
      THEN l2.treat_fluortag_norm
    ELSE l2.treat_fluortag_norm || ' > ' || l2.gt_fluortag_norm
  END AS tx_gt_fluortag,
  CASE
    WHEN COALESCE(NULLIF(btrim(COALESCE(l2.treat_organelle_norm,'')), ''), NULL) IS NULL
     AND COALESCE(NULLIF(btrim(COALESCE(l2.gt_organelle_norm,'')), ''), NULL) IS NULL
      THEN NULL
    WHEN COALESCE(NULLIF(btrim(COALESCE(l2.treat_organelle_norm,'')), ''), NULL) IS NULL
      THEN l2.gt_organelle_norm
    WHEN COALESCE(NULLIF(btrim(COALESCE(l2.gt_organelle_norm,'')), ''), NULL) IS NULL
      THEN l2.treat_organelle_norm
    ELSE l2.treat_organelle_norm || ' > ' || l2.gt_organelle_norm
  END AS tx_gt_fluororganelle
FROM fmt f
LEFT JOIN labels2 l2
  ON l2.roi_id = f.roi_id;

-- 2) Rewrite flat view to be 1 row per ROI (aggregate treatment/labels) + attach channel rollup.
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
  t.clutch_code,
  ch.n_channels_total,
  ch.n_channels_kept,
  ch.kept_channels_key;

COMMIT;
