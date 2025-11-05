BEGIN;
DO $$ BEGIN RAISE NOTICE '145900: superseded by newer marker/view migrations; skipping'; END $$;
COMMIT;
