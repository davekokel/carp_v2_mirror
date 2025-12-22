BEGIN;

-- ---------------------------------------------------------------------
-- 1) Genotype rollups: derive fluor-tag and organelle fluor labels from
--    genotypes_v11.genotype_basecodes via constructs -> fusions.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v11_genotype_label_star AS
WITH g AS (
  SELECT
    gv.id            AS genotype_v11_id,
    gv.genotype_code,
    gv.genotype_pretty,
    gv.genotype_basecodes
  FROM public.genotypes_v11 gv
),
tokens AS (
  SELECT
    g.genotype_v11_id,
    lower(btrim(tok)) AS base_code
  FROM g
  CROSS JOIN LATERAL regexp_split_to_table(
    coalesce(g.genotype_basecodes,''),
    '[,;|[:space:]]+'
  ) AS tok
  WHERE nullif(btrim(tok),'') IS NOT NULL
),
g_constructs AS (
  SELECT DISTINCT
    t.genotype_v11_id,
    c.id AS construct_id
  FROM tokens t
  JOIN public.constructs c
    ON lower(c.base_code) = t.base_code
),
fusion_bits AS (
  SELECT
    gc.genotype_v11_id,
    COALESCE(fl.nickname, fl.display_name, fl.code) AS fluor_label,
    COALESCE(tg.nickname, tg.display_name, tg.code) AS tag_label,
    tg.localization,
    f.tag_pos,
    CASE
      WHEN tg.id IS NULL THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format('%s-%s(%s)',
                  COALESCE(fl.nickname, fl.display_name, fl.code),
                  COALESCE(tg.nickname, tg.display_name, tg.code),
                  f.tag_pos)
    END AS fluor_tag_label,
    CASE
      WHEN tg.localization IS NULL OR tg.localization = '' THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format('%s-%s',
                  COALESCE(fl.nickname, fl.display_name, fl.code),
                  tg.localization)
    END AS organelle_fluor_label
  FROM g_constructs gc
  JOIN public.construct_fusions cf ON cf.construct_id = gc.construct_id
  JOIN public.fusions f           ON f.id = cf.fusion_id
  JOIN public.fluors fl           ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg        ON tg.id = f.tag_id
),
fluor_tag_rollup AS (
  SELECT
    genotype_v11_id,
    string_agg(DISTINCT fluor_tag_label, '; ' ORDER BY fluor_tag_label) AS all_fluor_tag_rollup
  FROM fusion_bits
  GROUP BY 1
),
organelle_fluor_rollup AS (
  SELECT
    genotype_v11_id,
    string_agg(DISTINCT organelle_fluor_label, '; ' ORDER BY organelle_fluor_label) AS all_organelle_fluor_rollup
  FROM fusion_bits
  GROUP BY 1
)
SELECT
  g.genotype_v11_id::uuid                         AS genotype_v11_id,
  g.genotype_code,
  g.genotype_pretty,
  g.genotype_basecodes,
  NULLIF(btrim(ft.all_fluor_tag_rollup),'')       AS fluor_tag_style,
  NULLIF(btrim(ofr.all_organelle_fluor_rollup),'') AS fluor_organelle_style
FROM g
LEFT JOIN fluor_tag_rollup ft       ON ft.genotype_v11_id = g.genotype_v11_id
LEFT JOIN organelle_fluor_rollup ofr ON ofr.genotype_v11_id = g.genotype_v11_id
;

-- ---------------------------------------------------------------------
-- 2) Replace ROI flat display: keep existing columns, and add tx_gt_*
--    using:
--      - treatment side: v11_treatment_label_star (treatment_display + rollups)
--      - genotype side : genotypes_v11 + v11_genotype_label_star
-- ---------------------------------------------------------------------
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
    NULLIF(btrim(tg.treatment_label_tg_style), '')            AS tg_style,
    NULLIF(btrim(tg.treatment_label_fluortag_style), '')      AS ft_style,
    NULLIF(btrim(tg.treatment_label_fluororganelle_style), '') AS fo_style
  FROM public.imaging_roi_annotations ra
  LEFT JOIN public.v11_imaging_plate_slot_overview ps ON ps.slot_id::uuid = ra.slot_id
  LEFT JOIN public.imaging_clutch_memberships m ON m.slot_id = ra.slot_id
  LEFT JOIN public.v11_treated_clutch_genotype_star_labels tg ON tg.treated_clutch_id = m.treated_clutch_id
),
clean AS (
  SELECT
    base.*,
    NULLIF(btrim(regexp_replace(COALESCE(base.tg_style,''), '^.*>[[:space:]]*', '')), '') AS tg_label,
    NULLIF(btrim(regexp_replace(COALESCE(base.ft_style,''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluortag_label,
    NULLIF(btrim(regexp_replace(COALESCE(base.fo_style,''), '^[[:space:]]*>[[:space:]]*', '')), '') AS fluororganelle_label_raw,
    (regexp_match(COALESCE(base.treatment_text,''), '(?i)(?:^|\\|)plasmids?=([^|]*)'))[1] AS plasmids_raw,
    (regexp_match(COALESCE(base.treatment_text,''), '(?i)(?:^|\\|)rnas?=([^|]*)'))[1]     AS rnas_raw,
    (regexp_match(COALESCE(base.treatment_text,''), '(?i)(?:^|\\|)dyes?=([^|]*)'))[1]     AS dyes_raw
  FROM base
),
fmt AS (
  SELECT
    clean.roi_path,
    clean.roi_note_anatomy,
    clean.slot_orientation,
    clean.plate_note,
    clean.slot_note,
    clean.experiment_name,
    clean.experiment_date,
    clean.roi_code,
    clean.roi_index_within_slot,
    clean.clutch_code,
    clean.treated_clutch_code,
    clean.treated_clutch_id,
    clean.treatment_code,
    clean.treatment_text,
    clean.tg_label,
    clean.fluortag_label,
    NULLIF(btrim(split_part(COALESCE(clean.fluororganelle_label_raw,''), '>', 1)), '') AS fluororganelle_name,
    NULLIF(btrim(split_part(COALESCE(clean.fluororganelle_label_raw,''), '>', 2)), '') AS fluororganelle_basecodes,
    NULLIF(btrim(clean.plasmids_raw), '') AS plasmids_basecodes,
    NULLIF(btrim(clean.rnas_raw), '')     AS rnas_basecodes,
    NULLIF(btrim(clean.dyes_raw), '')     AS dyes_codes,
    CASE WHEN NULLIF(btrim(clean.plasmids_raw), '') IS NULL THEN NULL
         ELSE 'plasmid(' || regexp_replace(btrim(clean.plasmids_raw), '\s*[;,]\s*|\s+', '), plasmid(', 'g') || ')'
    END AS plasmids_display,
    CASE WHEN NULLIF(btrim(clean.rnas_raw), '') IS NULL THEN NULL
         ELSE 'rna(' || regexp_replace(btrim(clean.rnas_raw), '\s*[;,]\s*|\s+', '), rna(', 'g') || ')'
    END AS rnas_display,
    CASE WHEN NULLIF(btrim(clean.dyes_raw), '') IS NULL THEN NULL
         ELSE 'dye(' || regexp_replace(btrim(clean.dyes_raw), '\s*[;,]\s*|\s+', '), dye(', 'g') || ')'
    END AS dyes_display
  FROM clean
),
gx AS (
  SELECT
    c.clutch_code,
    c.genotype_v11_id
  FROM public.clutches c
),
tx AS (
  SELECT
    tc.treated_clutch_code,
    tc.treatment_id
  FROM public.treated_clutches_v11 tc
),
labels AS (
  SELECT
    f.roi_code,

    -- treatment side
    tls.treatment_display,
    tls.fluor_tag_style        AS treat_fluortag_raw,
    tls.fluor_organelle_style  AS treat_organelle_raw,

    -- genotype side
    gv.genotype_pretty,
    gls.fluor_tag_style       AS gt_fluortag,
    gls.fluor_organelle_style AS gt_organelle,

    -- tx_gt_tg already proven good
    CASE
      WHEN nullif(btrim(coalesce(tls.treatment_display,'')),'') IS NULL THEN NULL
      WHEN nullif(btrim(coalesce(gv.genotype_pretty,'')),'') IS NULL THEN tls.treatment_display
      ELSE tls.treatment_display || ' > ' || gv.genotype_pretty
    END AS tx_gt_tg,

    -- wrap treatment fluor/organelle with delivery when unambiguous
    CASE
      WHEN nullif(btrim(coalesce(tls.fluor_tag_style,'')),'') IS NULL THEN NULL
      WHEN tls.treatment_display ILIKE 'rna(%' AND tls.treatment_display NOT ILIKE '%plasmid(%' THEN 'rna(' || tls.fluor_tag_style || ')'
      WHEN tls.treatment_display ILIKE 'plasmid(%' AND tls.treatment_display NOT ILIKE '%rna(%' THEN 'plasmid(' || tls.fluor_tag_style || ')'
      ELSE tls.fluor_tag_style
    END AS treat_fluortag_disp,

    CASE
      WHEN nullif(btrim(coalesce(tls.fluor_organelle_style,'')),'') IS NULL THEN NULL
      WHEN tls.treatment_display ILIKE 'rna(%' AND tls.treatment_display NOT ILIKE '%plasmid(%' THEN 'rna(' || tls.fluor_organelle_style || ')'
      WHEN tls.treatment_display ILIKE 'plasmid(%' AND tls.treatment_display NOT ILIKE '%rna(%' THEN 'plasmid(' || tls.fluor_organelle_style || ')'
      ELSE tls.fluor_organelle_style
    END AS treat_organelle_disp

  FROM fmt f
  LEFT JOIN gx ON gx.clutch_code = f.clutch_code
  LEFT JOIN public.genotypes_v11 gv ON gv.id = gx.genotype_v11_id
  LEFT JOIN public.v11_genotype_label_star gls ON gls.genotype_v11_id = gx.genotype_v11_id
  LEFT JOIN tx ON tx.treated_clutch_code = f.treated_clutch_code
  LEFT JOIN public.v11_treatment_label_star tls ON tls.treatment_id::uuid = tx.treatment_id
)
SELECT
  f.roi_path,
  f.roi_note_anatomy,
  f.slot_orientation,
  f.plate_note,
  f.slot_note,
  f.experiment_name,
  f.experiment_date,
  f.roi_code,
  f.roi_index_within_slot,
  f.clutch_code,
  f.treated_clutch_code,
  f.treated_clutch_id,
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

  -- NEW: the three fields you care about
  l.tx_gt_tg,
  CASE
    WHEN l.treat_fluortag_disp IS NULL THEN NULL
    WHEN nullif(btrim(coalesce(l.gt_fluortag,'')),'') IS NULL THEN l.treat_fluortag_disp
    ELSE l.treat_fluortag_disp || ' > ' || l.gt_fluortag
  END AS tx_gt_fluortag,
  CASE
    WHEN l.treat_organelle_disp IS NULL THEN NULL
    WHEN nullif(btrim(coalesce(l.gt_organelle,'')),'') IS NULL THEN l.treat_organelle_disp
    ELSE l.treat_organelle_disp || ' > ' || l.gt_organelle
  END AS tx_gt_fluororganelle

FROM fmt f
LEFT JOIN labels l ON l.roi_code = f.roi_code
;

COMMIT;
