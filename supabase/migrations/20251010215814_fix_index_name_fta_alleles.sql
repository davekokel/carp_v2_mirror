-- Idempotent: rename only if the old name exists and the new name does not
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    WHERE c.relname = 'idx_fish_transgene_alles_base_allele' AND c.relkind = 'i'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_class c
    WHERE c.relname = 'idx_fish_transgene_alleles_base_allele' AND c.relkind = 'i'
  ) THEN
    EXECUTE 'ALTER INDEX idx_fish_transgene_alles_base_allele RENAME TO idx_fish_transgene_alleles_base_allele';
  END IF;
END $$;
BEGIN
  IF to_regclass('public.idx_fish_transgene_alles_base_allele') IS NOT NULL
     AND to_regclass('public.idx_fish_transgene_alleles_base_allele') IS NULL THEN
    EXECUTE 'ALTER INDEX public.idx_fish_transgene_alles_base_allele RENAME TO idx_fish_transgene_alleles_base_allele';
  ELSE
    RAISE NOTICE 'index rename skipped (already renamed or not present)';
  END IF;
END $$;
