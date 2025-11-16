BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview;

CREATE VIEW public.v_roi_overview AS
WITH fusion_genotype AS (
  -- Fusions from parental plasmids (female + male)
  SELECT
    ir.id AS imaging_roi_id,
    string_agg(DISTINCT vl.fusion_label, '; ' ORDER BY vl.fusion_label) AS fusion_labels
  FROM imaging_rois ir
  JOIN raw.imaging_rois_raw r ON r.id = ir.raw_id
  LEFT JOIN plasmids pf ON pf.code = r.female_plasmid_base_code
  LEFT JOIN join_plasmid_fusions jpf_f ON jpf_f.plasmid_id = pf.id
  LEFT JOIN v_fusion_labels vl_f ON vl_f.fusion_id = jpf_f.fusion_id

  LEFT JOIN plasmids pm ON pm.code = r.male_plasmid_base_code
  LEFT JOIN join_plasmid_fusions jpf_m ON jpf_m.plasmid_id = pm.id
  LEFT JOIN v_fusion_labels vl_m ON vl_m.fusion_id = jpf_m.fusion_id

  LEFT JOIN LATERAL (
    SELECT COALESCE(vl_f.fusion_label, '') AS lab_f,
           COALESCE(vl_m.fusion_label, '') AS lab_m
  ) AS labs ON TRUE

  GROUP BY ir.id
),
fusion_injected AS (
  -- Fusions from injected plasmids + injected RNAs (via base codes)
  SELECT
    ir.id AS imaging_roi_id,
    string_agg(DISTINCT vl.fusion_label, '; ' ORDER BY vl.fusion_label) AS fusion_labels
  FROM imaging_rois ir
  JOIN raw.imaging_rois_raw r ON r.id = ir.raw_id
  LEFT JOIN plasmids pi ON pi.code = r.additional_plasmids_plasmid_base_code
  LEFT JOIN join_plasmid_fusions jpf_i ON jpf_i.plasmid_id = pi.id
  LEFT JOIN v_fusion_labels vl_pi ON vl_pi.fusion_id = jpf_i.fusion_id

  LEFT JOIN rnas rr ON rr.rna_base_code = r.additional_mrnas_plasmid_base_code
  LEFT JOIN join_rna_fusions jrf_i ON jrf_i.rna_id = rr.id
  LEFT JOIN v_fusion_labels vl_ri ON vl_ri.fusion_id = jrf_i.fusion_id

  GROUP BY ir.id
),
dyes_per_roi AS (
  SELECT
    ir.id AS imaging_roi_id,
    string_agg(DISTINCT dy.dye_base_code, '; ' ORDER BY dy.dye_base_code) AS dye_labels
  FROM imaging_rois ir
  JOIN raw.imaging_rois_raw r ON r.id = ir.raw_id
  LEFT JOIN dyes dy ON dy.dye_base_code = r.additonal_dye_dye_base_code
  GROUP BY ir.id
)
SELECT
  ir.id          AS imaging_roi_id,
  ir.dataset,
  ir.experiment_name,
  ir.fish_label,
  ir.fish_id,
  ir.roi_index,
  ir.roi_name,
  ir.roi_dir,
  ir.data_location,
  ir.mount_row_index_scored,
  ir.mount_id,
  ir.date_experiment,
  ir.date_mount,
  ir.raw_id,

  r.zf_female_genotype,
  r.zf_male_genotype,
  r.additional_plasmids_injected,
  r.additional_mrnas_injected,
  r.additonal_dye_and_chemicals,
  r.female_plasmid_base_code,
  r.female_allele,
  r.male_plasmid_base_code,
  r.male_allele,
  r.additional_plasmids_plasmid_base_code,
  r.additional_mrnas_plasmid_base_code,
  r.additonal_dye_dye_base_code,

  p.plasmid_base_code AS inj_plasmid_base_code,
  NULL::text          AS inj_plasmid_name,
  rn.rna_base_code    AS inj_rna_base_code,
  NULL::text          AS inj_rna_name,
  dy.dye_base_code    AS inj_dye_base_code,
  NULL::text          AS inj_dye_name,

  -- existing rollups from eq. genotype/treatment/dye codes
  roll.genotype_codes_group,
  roll.genotype_fusions_rollup,
  roll.allele_names_rollup,
  roll.treatments_codes_group,
  roll.treatments_names_group,

  -- TRUE fusion labels from genotype (via fusions table)
  gf.fusion_labels AS fluors_rollup,

  -- full marker rollup: genotype fusions + treatment fusions + dyes
  TRIM(BOTH '; ' FROM (
    COALESCE(gf.fusion_labels, '') ||
    CASE WHEN gf.fusion_labels IS NOT NULL AND tf.fusion_labels IS NOT NULL THEN '; ' ELSE '' END ||
    COALESCE(tf.fusion_labels, '') ||
    CASE WHEN (gf.fusion_labels IS NOT NULL OR tf.fusion_labels IS NOT NULL) AND dp.dye_labels IS NOT NULL THEN '; ' ELSE '' END ||
    COALESCE(dp.dye_labels, '')
  )) AS markers_rollup,

  (
    SELECT string_agg(
             'Tg(' || jfta.transgene_base_code || ')' || ta.allele_name,
             '; ' ORDER BY jfta.transgene_base_code, jfta.allele_number
           )
    FROM join_fish_transgene_alleles jfta
    JOIN transgene_alleles ta
      ON ta.transgene_base_code = jfta.transgene_base_code
     AND ta.allele_number       = jfta.allele_number
    WHERE jfta.fish_id = ir.fish_id
  ) AS genotype_alleles_rollup

FROM imaging_rois ir
JOIN raw.imaging_rois_raw r
  ON r.id = ir.raw_id
LEFT JOIN plasmids p
  ON p.plasmid_base_code = r.additional_plasmids_plasmid_base_code
LEFT JOIN rnas rn
  ON rn.rna_base_code = r.additional_mrnas_plasmid_base_code
LEFT JOIN dyes dy
  ON dy.dye_base_code = r.additonal_dye_dye_base_code

LEFT JOIN LATERAL (
  SELECT
    (
      SELECT string_agg(DISTINCT v.code, '; ' ORDER BY v.code)
      FROM (
        VALUES
          (r.female_plasmid_base_code),
          (r.male_plasmid_base_code),
          (r.additional_plasmids_plasmid_base_code),
          (r.additional_mrnas_plasmid_base_code),
          (r.additonal_dye_dye_base_code),
          (p.plasmid_base_code),
          (rn.rna_base_code),
          (dy.dye_base_code)
      ) AS v(code)
      WHERE v.code IS NOT NULL AND btrim(v.code) <> ''
    ) AS genotype_codes_group,
    (
      SELECT string_agg(DISTINCT t.t, '; ' ORDER BY t.t)
      FROM regexp_split_to_table(
             COALESCE(r.zf_female_genotype, '') || ',' || COALESCE(r.zf_male_genotype, ''),
             '[,;]'
           ) AS t(t)
      WHERE btrim(t.t) <> ''
    ) AS genotype_fusions_rollup,
    (
      SELECT string_agg(DISTINCT v.a, '; ' ORDER BY v.a)
      FROM (VALUES (r.female_allele), (r.male_allele)) AS v(a)
      WHERE v.a IS NOT NULL AND btrim(v.a) <> ''
    ) AS allele_names_rollup,
    (
      SELECT string_agg(DISTINCT v.code, '; ' ORDER BY v.code)
      FROM (
        VALUES
          (r.additional_plasmids_plasmid_base_code),
          (r.additional_mrnas_plasmid_base_code),
          (r.additonal_dye_dye_base_code),
          (dy.dye_base_code)
      ) AS v(code)
      WHERE v.code IS NOT NULL AND btrim(v.code) <> ''
    ) AS treatments_codes_group,
    (
      SELECT string_agg(DISTINCT t.t, '; ' ORDER BY t.t)
      FROM regexp_split_to_table(
             COALESCE(r.additional_plasmids_injected, '') || ',' ||
             COALESCE(r.additional_mrnas_injected, '')   || ',' ||
             COALESCE(r.additonal_dye_and_chemicals, ''),
             '[,;]'
           ) AS t(t)
      WHERE btrim(t.t) <> ''
    ) AS treatments_names_group
) AS roll ON TRUE

LEFT JOIN fusion_genotype gf ON gf.imaging_roi_id = ir.id
LEFT JOIN fusion_injected tf ON tf.imaging_roi_id = ir.id
LEFT JOIN dyes_per_roi dp ON dp.imaging_roi_id = ir.id;

COMMIT;
