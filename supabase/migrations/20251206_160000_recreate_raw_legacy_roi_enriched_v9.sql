BEGIN;

DROP TABLE IF EXISTS raw.legacy_roi_enriched_v9;

CREATE TABLE raw.legacy_roi_enriched_v9 (
  -- identity / keys
  legacy_clutch_key                 text,
  dataset                           text,
  experiment_name                   text,
  fish_label                        text,
  fish_number                       integer,
  fish_age_hpf                      integer,
  date_experiment                   text,
  date_mount_yyyymmdd               text,
  date_mount                        text,
  date_imaged                       text,
  date_born_from_enrich             text,

  -- plate / slot / ROI placement
  roi_name                          text,
  roi_index_within_slot             integer,
  roi_tiffs                         integer,
  roi_dir                           text,
  roi_folder                        text,
  plate_date                        text,
  plate_key                         text,
  plate_id_filled                   text,
  slot_id_filled                    text,
  mount_id                          text,
  mount_id_inferred                 text,
  mount_id_source                   text,
  bruker_roi_id                     text,

  -- anatomy / locations
  roi_anatomy_tokens                text,
  roi_anatomy                       text,
  imaged_locations                  text,
  all_unique_organelles             text,
  all_fluor_organelles              text,

  -- parent genotypes (enriched)
  zf_female_genotype_from_enrich    text,
  zf_male_genotype_from_enrich      text,

  -- child genotype basecodes / alleles (raw + slug)
  genotype_base_codes_slug          text,
  genotype_allele_codes_slug        text,
  genotype_base_codes               text,
  genotype_allele_codes             text,

  -- child genotype marker rollups (from enrichment)
  genotype_marker_fluor_codes       text,
  genotype_marker_tag_codes         text,
  genotype_marker_localizations     text,
  genotype_marker_fusion_labels     text,

  -- treatment names / codes (sheet-level)
  treatment_rna_names_sheet         text,
  treatment_plasmid_names_sheet     text,
  treatment_rna_codes_row           text,
  treatment_plasmid_codes_row       text,

  -- treatment basecodes (raw + enriched)
  treatment_rna_base_codes_slug     text,
  treatment_rna_rna_base_code       text,
  treatment_rna_rna_base_code_from_enrich      text,
  treatment_plasmid_plasmid_base_code          text,
  treatment_plasmid_plasmid_base_code_from_enrich text,

  -- treatment marker rollups (from enrichment)
  treatment_marker_fluor_codes      text,
  treatment_marker_tag_codes        text,
  treatment_marker_localizations    text,
  treatment_marker_fluor_loc_labels text
);

COMMENT ON TABLE raw.legacy_roi_enriched_v9 IS
'Enriched legacy ROI-level annotations (parents, basecodes, alleles, treatment basecodes, marker rollups) imported from legacy_imaging_annotations_for_db_v9.csv.';

COMMIT;
