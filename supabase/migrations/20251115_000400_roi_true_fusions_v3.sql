BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview CASCADE;
DROP VIEW IF EXISTS public.v_base_code_fusions CASCADE;
DROP VIEW IF EXISTS public.v_legacy_pair_genotype_fusions CASCADE;
DROP VIEW IF EXISTS public.v_legacy_clutch_genotype_fusions CASCADE;
DROP VIEW IF EXISTS public.v_legacy_clutch_treatment_fusions CASCADE;

CREATE VIEW public.v_base_code_fusions AS
SELECT DISTINCT
  COALESCE(p.plasmid_base_code, p.code) AS base_code,
  concat_ws(
    '::',
    COALESCE(fl.fluor_name, fl.fluor_code),
    COALESCE(t.tag_name,   t.tag_code)
  ) AS fusion_label
FROM public.plasmids p
JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
JOIN public.fusions f                ON f.id = jpf.fusion_id
LEFT JOIN public.fluors fl           ON fl.id = f.fluor_id
LEFT JOIN public.tags t              ON t.id = f.tag_id

UNION

SELECT DISTINCT
  COALESCE(
    r.rna_base_code,
    regexp_replace(r.rna_code, '^RNA\\(([^)]+)\\).*$', '\\1')
  ) AS base_code,
  concat_ws(
    '::',
    COALESCE(fl.fluor_name, fl.fluor_code),
    COALESCE(t.tag_name,   t.tag_code)
  ) AS fusion_label
FROM public.rnas r
JOIN public.join_rna_fusions jrf ON jrf.rna_id = r.id
JOIN public.fusions f            ON f.id = jrf.fusion_id
LEFT JOIN public.fluors fl       ON fl.id = f.fluor_id
LEFT JOIN public.tags t          ON t.id = f.tag_id

UNION

SELECT DISTINCT
  d.dye_base_code AS base_code,
  d.dye_name      AS fusion_label
FROM public.dyes d
WHERE d.dye_base_code IS NOT NULL;

CREATE VIEW public.v_legacy_pair_genotype_fusions AS
WITH pg AS (
  SELECT DISTINCT
    lp.id AS legacy_pair_id,
    NULLIF(pg.plasmid_base_code, 'NaN') AS base_code
  FROM public.legacy_pairs lp
  JOIN raw.parent_genotypes_raw pg
    ON pg.parent_fish_name IN (lp.zf_female_genotype, lp.zf_male_genotype)
  WHERE pg.plasmid_base_code IS NOT NULL
    AND pg.plasmid_base_code <> ''
    AND pg.plasmid_base_code <> 'n/a'
),
labels AS (
  SELECT
    pg.legacy_pair_id,
    pg.base_code,
    COALESCE(f.fusion_label, pg.base_code) AS fusion_label
  FROM pg
  LEFT JOIN public.v_base_code_fusions f
    ON f.base_code = pg.base_code
)
SELECT
  legacy_pair_id,
  string_agg(DISTINCT base_code,    ', ' ORDER BY base_code)    AS genotype_codes_group,
  string_agg(DISTINCT fusion_label, ', ' ORDER BY fusion_label) AS genotype_fusions_group
FROM labels
GROUP BY legacy_pair_id;

CREATE VIEW public.v_legacy_clutch_genotype_fusions AS
SELECT
  lc.id AS legacy_clutch_id,
  lpg.genotype_codes_group,
  lpg.genotype_fusions_group
FROM public.legacy_clutches lc
JOIN public.v_legacy_pair_genotype_fusions lpg
  ON lpg.legacy_pair_id = lc.legacy_pair_id;

CREATE VIEW public.v_legacy_clutch_treatment_fusions AS
WITH codes AS (
  SELECT
    ir.legacy_clutch_id,
    unnest(
      array[
        NULLIF(r.additional_plasmids_plasmid_base_code, 'NaN'),
        NULLIF(r.additional_mrnas_plasmid_base_code,    'NaN'),
        NULLIF(r.additonal_dye_dye_base_code,           'NaN')
      ]
    ) AS base_code
  FROM public.imaging_rois ir
  JOIN raw.imaging_rois_raw r
    ON r.id = ir.raw_id
  WHERE ir.legacy_clutch_id IS NOT NULL
),
labels AS (
  SELECT
    c.legacy_clutch_id,
    c.base_code,
    COALESCE(f.fusion_label, c.base_code) AS fusion_label
  FROM codes c
  LEFT JOIN public.v_base_code_fusions f
    ON f.base_code = c.base_code
)
SELECT
  legacy_clutch_id,
  string_agg(DISTINCT base_code,    ', ' ORDER BY base_code)    AS treatments_codes_group,
  string_agg(DISTINCT fusion_label, ', ' ORDER BY fusion_label) AS treatments_fusions_group
FROM labels
WHERE base_code IS NOT NULL
  AND base_code <> ''
  AND base_code <> 'n/a'
GROUP BY legacy_clutch_id;

CREATE VIEW public.v_roi_overview AS
SELECT
  ir.id                      AS imaging_roi_id,
  ir.dataset,
  ir.experiment_name,
  ir.fish_label,
  ir.roi_index,
  ir.roi_name,
  ir.roi_dir,
  ir.data_location,
  ir.mount_row_index_scored,
  ir.mount_id,
  ir.date_experiment,
  ir.date_mount,
  ir.date_born,
  ir.time_mounted,
  ir.mounting_orientation,
  ir.date_screened_initial_feedback,
  ir.date_imaged,
  ir.raw_id,

  ir.legacy_pair_id,
  lp.pair_code   AS legacy_pair_code,
  ir.legacy_clutch_id,
  lc.clutch_code AS legacy_clutch_code,

  r.zf_female_genotype,
  r.zf_male_genotype,
  r.additional_plasmids_injected,
  r.additional_mrnas_injected,
  r.additonal_proteins_injected,
  r.additonal_dye_and_chemicals,
  r.female_plasmid_base_code,
  r.female_allele,
  r.male_plasmid_base_code,
  r.male_allele,
  r.additional_plasmids_plasmid_base_code,
  r.additional_mrnas_plasmid_base_code,

  NULLIF(r.additional_plasmids_plasmid_base_code, 'NaN') AS inj_plasmid_base_code,
  NULLIF(r.additional_mrnas_plasmid_base_code,    'NaN') AS inj_rna_base_code,

  g.genotype_codes_group,
  t.treatments_codes_group,
  CASE
    WHEN t.treatments_codes_group IS NULL AND g.genotype_codes_group IS NULL
      THEN NULL
    ELSE coalesce(t.treatments_codes_group, '') || '  >  ' || coalesce(g.genotype_codes_group, '')
  END AS treatment_vs_genotype_codes,

  g.genotype_fusions_group,
  t.treatments_fusions_group,
  CASE
    WHEN t.treatments_fusions_group IS NULL AND g.genotype_fusions_group IS NULL
      THEN NULL
    ELSE coalesce(t.treatments_fusions_group, '') || '  >  ' || coalesce(g.genotype_fusions_group, '')
  END AS treatment_vs_genotype_fusions

FROM public.imaging_rois   ir
JOIN raw.imaging_rois_raw  r
  ON r.id = ir.raw_id
LEFT JOIN public.legacy_pairs lp
  ON lp.id = ir.legacy_pair_id
LEFT JOIN public.legacy_clutches lc
  ON lc.id = ir.legacy_clutch_id
LEFT JOIN public.plasmids p
  ON p.plasmid_base_code = NULLIF(r.additional_plasmids_plasmid_base_code, 'NaN')
LEFT JOIN public.rnas rn
  ON rn.rna_base_code = NULLIF(r.additional_mrnas_plasmid_base_code, 'NaN')
LEFT JOIN public.dyes dy
  ON dy.dye_base_code = NULLIF(r.additonal_dye_dye_base_code, 'NaN')
LEFT JOIN public.v_legacy_clutch_genotype_fusions g
  ON g.legacy_clutch_id = ir.legacy_clutch_id
LEFT JOIN public.v_legacy_clutch_treatment_fusions t
  ON t.legacy_clutch_id = ir.legacy_clutch_id;

COMMIT;
