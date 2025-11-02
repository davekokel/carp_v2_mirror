BEGIN;
DO $$ BEGIN
  RAISE NOTICE 'Skipping legacy migration 20251102_153500_rebuild_vci_codes_and_tokens.sql';
END $$;
COMMIT;
