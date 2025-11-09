BEGIN;

-- 1) Helpful index for the new composite FK (join_fish_transgene_alleles → transgene_alleles)
CREATE INDEX IF NOT EXISTS ix_jfta_base_num
  ON public.join_fish_transgene_alleles (transgene_base_code, allele_number);

-- 2) Natural key guards (idempotent)
CREATE UNIQUE INDEX IF NOT EXISTS uq_plasmids_code
  ON public.plasmids(code);

CREATE UNIQUE INDEX IF NOT EXISTS uq_treated_clutches_code
  ON public.treated_clutches(treated_clutch_code);

-- 3) Optional: reset raw schema (comment out if you want to keep current staging tables)
-- DROP SCHEMA IF EXISTS raw CASCADE;
-- CREATE SCHEMA raw;

COMMIT;
