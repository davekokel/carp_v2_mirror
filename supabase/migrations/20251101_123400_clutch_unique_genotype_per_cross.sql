BEGIN;
/*
  Rebuild-safe: legacy migration targeted clutch_instances (now a view).
  Skipping — clutches is canonical and later migrations implement the logic.
*/
DO $$ BEGIN
  RAISE NOTICE '123400: legacy clutch_instances ALTER skipped (clutches is canonical)';
END $$;
COMMIT;
