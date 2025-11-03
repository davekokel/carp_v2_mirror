BEGIN;
DO $$ BEGIN RAISE NOTICE '185322: legacy clutch rewrite/drop skipped (superseded by later normalized migrations)'; END $$;
COMMIT;
