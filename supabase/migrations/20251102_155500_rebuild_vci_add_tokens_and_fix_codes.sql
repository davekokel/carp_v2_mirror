BEGIN;
DO $$ BEGIN
  RAISE NOTICE 'Skipping legacy migration 20251102_155500_rebuild_vci_add_tokens_and_fix_codes.sql';
END $$;
COMMIT;
