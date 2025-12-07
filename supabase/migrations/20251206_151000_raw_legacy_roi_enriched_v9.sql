BEGIN;

CREATE TABLE IF NOT EXISTS raw.legacy_roi_enriched_v9 (
  legacy_clutch_key  text,
  dataset            text,
  fish_label         text,
  date_mount         text,
  genotype_base_codes        text,
  genotype_allele_codes      text,
  zf_female_genotype_enrich  text,
  zf_male_genotype_enrich    text,
  treatment_rna_base_codes   text,
  treatment_plasmid_base_codes text
  -- add any other enriched columns you care about
);

COMMENT ON TABLE raw.legacy_roi_enriched_v9 IS
'Enriched legacy ROI-level annotations (parents, basecodes, alleles, treatment basecodes) imported from legacy_imaging_annotations_for_db_v9.csv.';

COMMIT;
