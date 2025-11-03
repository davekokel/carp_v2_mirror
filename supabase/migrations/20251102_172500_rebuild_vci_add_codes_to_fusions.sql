BEGIN;
/* Rebuild-safe: legacy clutch/JCT lineage migration skipped (superseded by normalized views) */
DO $$ BEGIN RAISE NOTICE legacy clutch/JCT lineage migration skipped; END $$;
COMMIT;
