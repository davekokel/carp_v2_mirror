BEGIN;

CREATE OR REPLACE VIEW public.v_legacy_roi_channels_v5 AS
SELECT
  c.roi_path,
  c.channel_name,
  c.n_tiffs,
  c.decision_status,
  c.note,
  m.date_mount_id,
  m.genotype_base_codes,
  m.genotype_allele_codes,
  m.treatment_rna_base_codes,
  m.treatment_plasmid_base_codes
FROM public.legacy_roi_channels_v5 c
JOIN public.legacy_roi_path_map_v5 m USING (roi_path);

COMMIT;
