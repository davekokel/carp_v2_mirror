BEGIN;
/*
  Rebuild-safe: legacy migration targeted clutch_instances (now a view).
  Skipping — clutches is canonical and newer migrations supersede this.
*/
DO $$ BEGIN
  RAISE NOTICE '123500: legacy clutch_instances ALTER skipped (clutches is canonical)';
END $$;
COMMIT;
