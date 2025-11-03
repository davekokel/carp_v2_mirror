BEGIN;
DO $$ BEGIN
  RAISE NOTICE 'Skipping legacy VCI migration';
END $$;
COMMIT;
