-- Idempotent: only rename if the old index exists and the new name does not

LANGUAGE plpgsql;
DO $$
BEGIN
  IF to_regclass('public.idx_fish_transgene_alles_base_allele') IS NOT NULL
     AND to_regclass('public.idx_fish_transgene_alleles_base_allele') IS NULL THEN
    EXECUTE 'ALTER INDEX public.idx_fish_transgene_alles_base_allele RENAME TO idx_fish_transgene_alleles_base_allele';
  ELSE
    RAISE NOTICE 'index rename skipped (already renamed or not present)';
  END IF;
END $$;
