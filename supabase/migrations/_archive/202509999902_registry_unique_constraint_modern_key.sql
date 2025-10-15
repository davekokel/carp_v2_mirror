BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.transgene_allele_registry'::regclass
      AND conname  = 'uq_registry_modern'
  ) THEN
    -- If duplicates exist, this will fail; better to catch early:
    IF EXISTS (
      SELECT 1
      FROM (
        SELECT transgene_base_code, allele_nickname, count(*) c
        FROM public.transgene_allele_registry
        GROUP BY 1,2
        HAVING count(*) > 1
      ) dups
    ) THEN
      RAISE EXCEPTION 'Cannot add UNIQUE constraint: duplicates exist in (transgene_base_code, allele_nickname)';
    END IF;

    ALTER TABLE public.transgene_allele_registry
      ADD CONSTRAINT uq_registry_modern
      UNIQUE (transgene_base_code, allele_nickname);
  END IF;
END$$;

COMMIT;
