BEGIN;

ALTER TABLE raw.imaging_rois_raw
  ADD COLUMN IF NOT EXISTS additonal_dye_dye_base_code text;

DROP VIEW IF EXISTS public.v_imaging_rois_rich;
DROP VIEW IF EXISTS public.v_roi_overview;

CREATE VIEW public.v_roi_overview AS
SELECT
  ir.id                      AS imaging_roi_id,
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

  p.plasmid_base_code           AS inj_plasmid_base_code,
  p.name                        AS inj_plasmid_name,
  p.nickname                    AS inj_plasmid_nickname,

  rn.rna_base_code              AS inj_rna_base_code,
  rn.name                       AS inj_rna_name,
  rn.nickname                   AS inj_rna_nickname,

  dy.dye_base_code              AS inj_dye_base_code,
  dy.name                       AS inj_dye_name,
  dy.nickname                   AS inj_dye_nickname,

  vfr.genotype_codes_group,
  vfr.genotype_fusions_rollup,
  vfr.allele_names_rollup,
  vfr.treatments_codes_group,
  vfr.treatments_names_group

FROM public.imaging_rois         ir
JOIN raw.imaging_rois_raw        r
  ON r.id = ir.raw_id
LEFT JOIN public.plasmids        p
  ON p.plasmid_base_code = r.additional_plasmids_plasmid_base_code
LEFT JOIN public.rnas            rn
  ON rn.rna_base_code = r.additional_mrnas_plasmid_base_code
LEFT JOIN public.dyes            dy
  ON dy.dye_base_code = r.additonal_dye_dye_base_code
LEFT JOIN public.v_fish_rich     vfr
  ON vfr.fish_id = ir.fish_id;

COMMIT;
