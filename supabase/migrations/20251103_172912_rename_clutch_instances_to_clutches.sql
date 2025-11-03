BEGIN;
/* Rebuild-safe: legacy ALTER on clutch_instances skipped (clutches is canonical) */
DO $$ BEGIN RAISE NOTICE 'legacy clutch_instances ALTER skipped'; END $$;
COMMIT;
