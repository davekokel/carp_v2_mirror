BEGIN;
DO $$ BEGIN
  RAISE NOTICE 'Skipping legacy migration 20251102_152500_rebuild_v_clutch_instances_use_token_codes.sql';
END $$;
COMMIT;
