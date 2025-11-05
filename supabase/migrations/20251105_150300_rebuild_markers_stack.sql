BEGIN;
DO $$ BEGIN RAISE NOTICE '150300: superseded by v4 marker/view migrations; skipping'; END $$;
COMMIT;
