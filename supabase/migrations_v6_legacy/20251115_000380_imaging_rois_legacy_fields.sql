BEGIN;

ALTER TABLE raw.imaging_rois_raw
  ADD COLUMN IF NOT EXISTS date_mount text,
  ADD COLUMN IF NOT EXISTS mount_id text,
  ADD COLUMN IF NOT EXISTS zf_female_genotype text,
  ADD COLUMN IF NOT EXISTS zf_male_genotype text,
  ADD COLUMN IF NOT EXISTS additional_plasmids_injected text,
  ADD COLUMN IF NOT EXISTS additional_mrnas_injected text,
  ADD COLUMN IF NOT EXISTS additonal_proteins_injected text,
  ADD COLUMN IF NOT EXISTS additonal_dye_and_chemicals text,
  ADD COLUMN IF NOT EXISTS date_born text,
  ADD COLUMN IF NOT EXISTS time_mounted text,
  ADD COLUMN IF NOT EXISTS mounting_orientation text,
  ADD COLUMN IF NOT EXISTS date_screened_initial_feedback text,
  ADD COLUMN IF NOT EXISTS date_imaged text,
  ADD COLUMN IF NOT EXISTS data_location text;

ALTER TABLE public.imaging_rois
  ADD COLUMN IF NOT EXISTS date_mount text,
  ADD COLUMN IF NOT EXISTS mount_id text,
  ADD COLUMN IF NOT EXISTS zf_female_genotype text,
  ADD COLUMN IF NOT EXISTS zf_male_genotype text,
  ADD COLUMN IF NOT EXISTS additional_plasmids_injected text,
  ADD COLUMN IF NOT EXISTS additional_mrnas_injected text,
  ADD COLUMN IF NOT EXISTS additonal_proteins_injected text,
  ADD COLUMN IF NOT EXISTS additonal_dye_and_chemicals text,
  ADD COLUMN IF NOT EXISTS date_born text,
  ADD COLUMN IF NOT EXISTS time_mounted text,
  ADD COLUMN IF NOT EXISTS mounting_orientation text,
  ADD COLUMN IF NOT EXISTS date_screened_initial_feedback text,
  ADD COLUMN IF NOT EXISTS date_imaged text,
  ADD COLUMN IF NOT EXISTS data_location text;

COMMIT;
