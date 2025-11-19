BEGIN;

CREATE TABLE IF NOT EXISTS public.imaging_roi_annotations (
  roi_dir                         text PRIMARY KEY,
  parent_female                   text,
  parent_male                     text,
  genotype_pretty                 text,
  genotype_base_codes             text,
  genotype_allele_codes           text,
  genotype_marker_fluor_codes     text,
  genotype_marker_tag_codes       text,
  treatment_plasmid_base_codes    text,
  treatment_rna_base_codes        text,
  treatment_dye_base_codes        text,
  treatment_marker_fluor_codes    text,
  treatment_marker_tag_codes      text,
  all_marker_fluor_codes          text,
  source_system                   text,
  import_batch_id                 text,
  created_at                      timestamptz DEFAULT now()
);

COMMIT;
