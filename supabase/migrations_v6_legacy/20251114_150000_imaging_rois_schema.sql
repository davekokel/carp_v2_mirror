BEGIN;

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.imaging_rois_raw (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  date_experiment text,
  fish_label text,
  roi_rel text,
  roi_name text,
  roi_tiffs integer,
  roi_dir text,
  dataset text,
  experiment_name text,
  mount_row_index_scored integer,
  date_mount text,
  mount_id text,
  zf_female_genotype text,
  zf_male_genotype text,
  additional_plasmids_injected text,
  additional_mrnas_injected text,
  additonal_dye_and_chemicals text,
  data_location text,
  female_plasmid_base_code text,
  female_allele text,
  male_plasmid_base_code text,
  male_allele text,
  additional_plasmids_plasmid_base_code text,
  additional_mrnas_plasmid_base_code text
);

CREATE TABLE IF NOT EXISTS public.imaging_rois (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_id uuid NULL REFERENCES public.fish(id),
  fish_label text NOT NULL,
  roi_index integer NOT NULL,
  roi_name text,
  roi_dir text NOT NULL,
  dataset text,
  experiment_name text,
  data_location text,
  mount_row_index_scored integer,
  mount_id text,
  date_experiment date,
  date_mount date,
  raw_id uuid NOT NULL REFERENCES raw.imaging_rois_raw(id),
  UNIQUE (fish_label, roi_index, dataset)
);

CREATE INDEX IF NOT EXISTS idx_imaging_rois_fish_id
  ON public.imaging_rois (fish_id);

COMMIT;
