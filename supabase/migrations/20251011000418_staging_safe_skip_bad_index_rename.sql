DO $$
BEGIN
  IF to_regclass('public.idx_fish_transgene_alles_base_allele') IS NOT NULL THEN
    EXECUTE 'ALTER INDEX IF EXISTS public.idx_fish_transgene_alles_base_allele RENAME TO idx_fish_transgene_alleles_base_allele';
  END IF;
END$$;
