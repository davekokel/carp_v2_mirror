BEGIN;

CREATE OR REPLACE VIEW public.v_imaging_parent_alleles AS
SELECT
  ir.id          AS raw_roi_id,
  ir.dataset,
  ir.experiment_name,
  ir.fish_label,
  ir.roi_name,

  ir.zf_female_genotype       AS mother_genotype_raw,
  m.plasmid_base_code         AS mother_plasmid_base_code,
  m.allele_nickname           AS mother_allele_nickname,

  ir.zf_male_genotype         AS father_genotype_raw,
  f.plasmid_base_code         AS father_plasmid_base_code,
  f.allele_nickname           AS father_allele_nickname

FROM raw.imaging_rois_raw ir
LEFT JOIN public.legacy_parent_to_allele m
  ON m.parent_fish_name = ir.zf_female_genotype
LEFT JOIN public.legacy_parent_to_allele f
  ON f.parent_fish_name = ir.zf_male_genotype;

COMMIT;
