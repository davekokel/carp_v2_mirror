BEGIN;

CREATE OR REPLACE VIEW public.v_legacy_roi_overview AS
SELECT
  r.id          AS raw_roi_id,
  r.dataset,
  r.experiment_name,
  r.fish_label,
  r.roi_rel      AS roi_rel,
  r.roi_name,
  r.roi_dir,
  r.mount_row_index_scored,
  r.date_mount,
  r.mount_id,
  r.zf_female_genotype,
  r.zf_male_genotype,
  r.additional_plasmids_injected,
  r.additional_mrnas_injected,
  r.additonal_dye_and_chemicals,
  r.data_location,

  -- normalized parents from legacy_parent_to_allele
  p.mother_genotype_raw,
  p.mother_plasmid_base_code,
  p.mother_allele_nickname,
  p.father_genotype_raw,
  p.father_plasmid_base_code,
  p.father_allele_nickname,

  -- normalized injections from injected maps
  inj.additional_plasmids_injected   AS norm_additional_plasmids_injected,
  inj.injected_plasmid_base_code,
  inj.additional_mrnas_injected      AS norm_additional_mrnas_injected,
  inj.injected_rna_base_code

FROM raw.imaging_rois_raw r
LEFT JOIN public.v_legacy_imaging_parent_alleles p
  ON p.raw_roi_id = r.id
LEFT JOIN public.v_legacy_imaging_injected inj
  ON inj.raw_roi_id = r.id;

COMMIT;
