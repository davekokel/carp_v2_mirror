BEGIN;

ALTER TABLE raw.legacy_clutch_transgene_alleles_v9
  ADD COLUMN IF NOT EXISTS allele_nickname text;

COMMIT;
