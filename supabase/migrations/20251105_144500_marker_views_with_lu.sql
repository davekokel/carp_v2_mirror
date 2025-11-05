BEGIN;
DO $$ BEGIN RAISE NOTICE '144500: marker LU/views already defined; skipping'; END $$;
COMMIT;
