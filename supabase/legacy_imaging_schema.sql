BEGIN;

CREATE TABLE IF NOT EXISTS raw.legacy_pairs_raw (
  dataset text,
  zf_female_genotype text,
  zf_male_genotype text,
  roi_count integer
);

CREATE TABLE IF NOT EXISTS raw.legacy_clutches_raw (
  dataset text,
  zf_female_genotype text,
  zf_male_genotype text,
  date_mount text,
  roi_count integer
);

CREATE TABLE IF NOT EXISTS raw.legacy_rois_raw (
  dataset text,
  experiment_name text,
  fish_label text,
  zf_female_genotype text,
  zf_male_genotype text,
  date_mount text,
  roi_index integer,
  roi_name text
);

CREATE TABLE IF NOT EXISTS public.legacy_pairs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset text NOT NULL,
  zf_female_genotype text NOT NULL,
  zf_male_genotype text NOT NULL,
  pair_code text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_legacy_pairs_dataset_parents
  ON public.legacy_pairs (dataset, zf_female_genotype, zf_male_genotype);

CREATE TABLE IF NOT EXISTS public.legacy_clutches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  legacy_pair_id uuid NOT NULL REFERENCES public.legacy_pairs(id) ON DELETE CASCADE,
  dataset text NOT NULL,
  date_mount text,
  clutch_code text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_legacy_clutches_pair_date
  ON public.legacy_clutches (legacy_pair_id, date_mount);

ALTER TABLE public.imaging_rois
  ADD COLUMN IF NOT EXISTS legacy_pair_id uuid REFERENCES public.legacy_pairs(id),
  ADD COLUMN IF NOT EXISTS legacy_clutch_id uuid REFERENCES public.legacy_clutches(id);

COMMIT;
