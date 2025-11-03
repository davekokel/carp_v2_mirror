BEGIN;
/* Rebuild-safe: legacy JCT norm columns skipped (we use treatment_id now) */
DO $$ BEGIN RAISE NOTICE '151200: legacy join_clutch_treatments norm cols skipped'; END $$;
COMMIT;
