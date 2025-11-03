BEGIN;
/*
  Rebuild-safe: this legacy migration tried to ALTER TABLE clutch_instances,
  but clutch_instances is now a view alias to clutches. Skip it.
*/
DO $$ BEGIN
  RAISE NOTICE '123200: legacy clutch_instances ALTER skipped (clutches is canonical)';
END $$;
COMMIT;
