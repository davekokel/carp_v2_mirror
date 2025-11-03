BEGIN;
/*
  Rebuild-safe patch:
  This file formerly dropped legacy columns on join_clutch_treatments.
  Those drops are performed by later migrations after views are rewritten.
  Keep this as a no-op so clean rebuilds pass.
*/
DO $$ BEGIN RAISE NOTICE '182248: legacy column drops skipped (handled by later migrations)'; END $$;
COMMIT;
