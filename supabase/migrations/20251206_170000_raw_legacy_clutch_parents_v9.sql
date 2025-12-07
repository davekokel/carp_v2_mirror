BEGIN;

DROP TABLE IF EXISTS raw.legacy_clutch_parents_v9;

CREATE TABLE raw.legacy_clutch_parents_v9 (
  clutch_code           text,
  date_born             date,
  parent_female_label   text,
  parent_male_label     text,
  parent_female_allele  integer,
  parent_male_allele    integer,
  legacy_clutch_group   text
);

COMMENT ON TABLE raw.legacy_clutch_parents_v9 IS
'Legacy clutch-level parent descriptors and parsed allele IDs from legacy_clutches_v9_for_loader.csv.';

COMMIT;
