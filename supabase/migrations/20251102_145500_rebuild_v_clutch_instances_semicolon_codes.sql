BEGIN;
DO $$ BEGIN
  RAISE NOTICE 'Skipping legacy migration 20251102_145500_rebuild_v_clutch_instances_semicolon_codes.sql';
END $$;
COMMIT;
