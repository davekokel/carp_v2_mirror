BEGIN;
DO $$ BEGIN
  RAISE NOTICE 'Skipping legacy migration 20251102_145900_rebuild_v_clutch_instances_semicolon_codes_fix.sql';
END $$;
COMMIT;
