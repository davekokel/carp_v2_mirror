BEGIN;

CREATE TABLE IF NOT EXISTS raw.legacy_clutch_transgene_alleles_v9 (
  clutch_code          text,
  clutch_id            uuid,
  parent_role          text,
  parent_label         text,
  transgene_base_code  text,
  allele_number        integer,
  transgene_allele_id  uuid
);

COMMENT ON TABLE raw.legacy_clutch_transgene_alleles_v9 IS
'Legacy v9 clutch → transgene allele mapping, derived from legacy_clutch_parents_v9 and legacy_parent_definitions_v9.';

COMMIT;
