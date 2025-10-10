DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    WHERE c.relname = 'idx_fish_transgene_alles_base_allele'
      AND c.relkind = 'i'
  ) THEN
    EXECUTE 'ALTER INDEX idx_fish_transgene_alles_base_allele RENAME TO idx_fish_transgene_alleles_base_allele';
  END IF;
END$$;
