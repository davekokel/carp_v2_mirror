BEGIN;

CREATE OR REPLACE VIEW public.v_roi_fusion_markers AS
WITH base AS (
  SELECT
    ir.id          AS imaging_roi_id,
    ir.dataset,
    ir.experiment_name,
    ir.fish_label,
    ir.roi_name,
    r.female_plasmid_base_code,
    r.male_plasmid_base_code,
    r.additional_plasmids_plasmid_base_code,
    r.additional_mrnas_plasmid_base_code,
    r.additonal_dye_dye_base_code
  FROM public.imaging_rois ir
  JOIN raw.imaging_rois_raw r ON r.id = ir.raw_id
),

genotype_fusions AS (
  -- fusions from female + male plasmids
  SELECT
    b.imaging_roi_id,
    string_agg(DISTINCT f_label, '; ' ORDER BY f_label) AS fusion_rollup_genotype
  FROM base b
  LEFT JOIN LATERAL (
    SELECT vl_f.fusion_label AS f_label
    FROM plasmids pf
    JOIN public.join_plasmid_fusions jpf_f ON jpf_f.plasmid_id = pf.id
    JOIN public.v_fusion_labels vl_f ON vl_f.fusion_id = jpf_f.fusion_id
    WHERE pf.plasmid_base_code = b.female_plasmid_base_code

    UNION

    SELECT vl_m.fusion_label AS f_label
    FROM plasmids pm
    JOIN public.join_plasmid_fusions jpf_m ON jpf_m.plasmid_id = pm.id
    JOIN public.v_fusion_labels vl_m ON vl_m.fusion_id = jpf_m.fusion_id
    WHERE pm.plasmid_base_code = b.male_plasmid_base_code
  ) AS fus ON TRUE
  GROUP BY b.imaging_roi_id
),

injected_fusions AS (
  -- fusions from injected plasmids + injected RNAs
  SELECT
    b.imaging_roi_id,
    string_agg(DISTINCT f_label, '; ' ORDER BY f_label) AS fusion_rollup_injected
  FROM base b
  LEFT JOIN LATERAL (
    SELECT vl_pi.fusion_label AS f_label
    FROM plasmids pi
    JOIN public.join_plasmid_fusions jpf_i ON jpf_i.plasmid_id = pi.id
    JOIN public.v_fusion_labels vl_pi ON vl_pi.fusion_id = jpf_i.fusion_id
    WHERE pi.plasmid_base_code = b.additional_plasmids_plasmid_base_code

    UNION

    SELECT vl_ri.fusion_label AS f_label
    FROM rnas rr
    JOIN public.join_rna_fusions jrf_i ON jrf_i.rna_id = rr.id
    JOIN public.v_fusion_labels vl_ri ON vl_ri.fusion_id = jrf_i.fusion_id
    WHERE rr.rna_base_code = b.additional_mrnas_plasmid_base_code
  ) AS fus ON TRUE
  GROUP BY b.imaging_roi_id
),

dyes AS (
  SELECT
    b.imaging_roi_id,
    string_agg(DISTINCT b.additonal_dye_dye_base_code, '; ' ORDER BY b.additonal_dye_dye_base_code) AS dyes_rollup
  FROM base b
  WHERE b.additonal_dye_dye_base_code IS NOT NULL
    AND btrim(b.additonal_dye_dye_base_code) <> ''
  GROUP BY b.imaging_roi_id
)

SELECT
  b.imaging_roi_id,
  b.dataset,
  b.experiment_name,
  b.fish_label,
  b.roi_name,
  gf.fusion_rollup_genotype,
  inj.fusion_rollup_injected,
  dy.dyes_rollup,
  TRIM(BOTH '; ' FROM
    COALESCE(gf.fusion_rollup_genotype, '') ||
    CASE WHEN gf.fusion_rollup_genotype IS NOT NULL AND inj.fusion_rollup_injected IS NOT NULL THEN '; ' ELSE '' END ||
    COALESCE(inj.fusion_rollup_injected, '') ||
    CASE WHEN (gf.fusion_rollup_genotype IS NOT NULL OR inj.fusion_rollup_injected IS NOT NULL)
           AND dy.dyes_rollup IS NOT NULL THEN '; ' ELSE '' END ||
    COALESCE(dy.dyes_rollup, '')
  ) AS markers_rollup
FROM base b
LEFT JOIN genotype_fusions gf ON gf.imaging_roi_id = b.imaging_roi_id
LEFT JOIN injected_fusions inj ON inj.imaging_roi_id = b.imaging_roi_id
LEFT JOIN dyes dy ON dy.imaging_roi_id = b.imaging_roi_id;

COMMIT;
