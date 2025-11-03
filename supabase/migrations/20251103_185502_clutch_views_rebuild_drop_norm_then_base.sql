BEGIN;
/* Rebuild-safe: legacy JCT {treatment_code|treatment_name} migration skipped (normalized to treatment_id) */
DO $$ BEGIN RAISE NOTICE 'legacy JCT text cols skipped'; END $$;
COMMIT;
