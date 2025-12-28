-- v5 legacy ROI marker import support
ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN IF NOT EXISTS v5_date_mount_id text,
  ADD COLUMN IF NOT EXISTS v5_genotype_base_codes text,
  ADD COLUMN IF NOT EXISTS v5_genotype_allele_codes text,
  ADD COLUMN IF NOT EXISTS v5_treatment_rna_base_codes text,
  ADD COLUMN IF NOT EXISTS v5_treatment_plasmid_base_codes text;

CREATE INDEX IF NOT EXISTS imaging_roi_annotations_roi_path_idx
  ON public.imaging_roi_annotations (roi_path);
