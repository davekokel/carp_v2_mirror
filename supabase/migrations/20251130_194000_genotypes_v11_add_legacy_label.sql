BEGIN;

ALTER TABLE public.genotypes_v11
  ADD COLUMN IF NOT EXISTS legacy_label text;

COMMENT ON COLUMN public.genotypes_v11.legacy_label IS
  'Legacy label for genotypes (e.g. LCL-0001) distinct from genotype_basecodes, which in v11 should be construct/transgene rollups.';

COMMIT;
