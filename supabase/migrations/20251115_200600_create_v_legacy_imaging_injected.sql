BEGIN;

CREATE OR REPLACE VIEW public.v_legacy_imaging_injected AS
SELECT
  ir.id          AS raw_roi_id,
  ir.dataset,
  ir.experiment_name,
  ir.fish_label,
  ir.roi_name,

  ir.additional_plasmids_injected,
  lip.plasmid_base_code   AS injected_plasmid_base_code,

  ir.additional_mrnas_injected,
  lir.plasmid_base_code   AS injected_rna_base_code

FROM raw.imaging_rois_raw ir
LEFT JOIN public.legacy_injected_plasmids_map lip
  ON lip.injected_plasmid = ir.additional_plasmids_injected
LEFT JOIN public.legacy_injected_rnas_map lir
  ON lir.injected_rna = ir.additional_mrnas_injected;

COMMIT;
