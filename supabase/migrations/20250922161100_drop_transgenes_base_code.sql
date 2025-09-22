BEGIN;

-- One-time sync just in case anything left the two columns out of sync.
UPDATE public.transgenes
SET transgene_base_code = COALESCE(transgene_base_code, base_code)
WHERE base_code IS NOT NULL;

-- Drop any remaining indexes on base_code (belt & suspenders)
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT i.indexname
    FROM pg_indexes i
    WHERE i.schemaname='public'
      AND i.tablename='transgenes'
      AND i.indexdef ILIKE '%(base_code%'
  LOOP
    EXECUTE format('DROP INDEX IF EXISTS %I', r.indexname);
  END LOOP;
END$$;

ALTER TABLE public.transgenes
  DROP COLUMN IF EXISTS base_code;

COMMIT;
