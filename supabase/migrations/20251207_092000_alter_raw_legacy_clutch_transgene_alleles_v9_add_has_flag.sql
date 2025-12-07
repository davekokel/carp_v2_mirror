BEGIN;

ALTER TABLE raw.legacy_clutch_transgene_alleles_v9
  ADD COLUMN IF NOT EXISTS has_transgene_allele boolean;

COMMIT;
