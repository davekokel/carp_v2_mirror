BEGIN;
/*
  Rebuild-safe patch:
  This migration used to drop legacy columns on join_clutch_treatments.
  We now defer ALL column drops to later files after views are rewritten.
  Keep this file as a no-op so clean rebuilds pass deterministically.
*/
DO $$ BEGIN RAISE NOTICE '182210: legacy column drops skipped (handled by later migrations)'; END $$;
COMMIT;
