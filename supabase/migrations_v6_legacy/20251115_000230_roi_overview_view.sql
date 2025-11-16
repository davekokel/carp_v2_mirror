BEGIN;

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
  date_experiment text,
  date_mount text,
  raw_id uuid NOT NULL REFERENCES raw.imaging_rois_raw(id),
  UNIQUE (fish_label, roi_index, dataset)
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'imaging_rois'
      AND column_name  = 'date_experiment'
      AND data_type   <> 'text'
  ) THEN
    ALTER TABLE public.imaging_rois
      ALTER COLUMN date_experiment TYPE text USING date_experiment::text;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'imaging_rois'
      AND column_name  = 'date_mount'
      AND data_type   <> 'text'
  ) THEN
    ALTER TABLE public.imaging_rois
      ALTER COLUMN date_mount TYPE text USING date_mount::text;
  END IF;
END $$;

ALTER TABLE public.plasmids
  ADD COLUMN IF NOT EXISTS plasmid_base_code text;

ALTER TABLE public.rnas
  ADD COLUMN IF NOT EXISTS rna_base_code text;

ALTER TABLE public.dyes
  ADD COLUMN IF NOT EXISTS dye_base_code text;

ALTER TABLE raw.imaging_rois_raw
  ADD COLUMN IF NOT EXISTS additonal_dye_dye_base_code text;

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
  NULL::text                    AS inj_plasmid_name,

  rn.rna_base_code              AS inj_rna_base_code,
  NULL::text                    AS inj_rna_name,

  dy.dye_base_code              AS inj_dye_base_code,
  NULL::text                    AS inj_dye_name,

  NULL::text                    AS genotype_codes_group,
  NULL::text                    AS genotype_fusions_rollup,
  NULL::text                    AS allele_names_rollup,
  NULL::text                    AS treatments_codes_group,
  NULL::text                    AS treatments_names_group

FROM public.imaging_rois   ir
JOIN raw.imaging_rois_raw  r
  ON r.id = ir.raw_id
LEFT JOIN public.plasmids  p
  ON p.plasmid_base_code = r.additional_plasmids_plasmid_base_code
LEFT JOIN public.rnas      rn
  ON rn.rna_base_code = r.additional_mrnas_plasmid_base_code
LEFT JOIN public.dyes      dy
  ON dy.dye_base_code = r.additonal_dye_dye_base_code;

COMMIT;
