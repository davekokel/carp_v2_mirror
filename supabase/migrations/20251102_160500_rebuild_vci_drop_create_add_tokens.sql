BEGIN;
DO $$ BEGIN
  RAISE NOTICE 'Skipping legacy migration 20251102_160500_rebuild_vci_drop_create_add_tokens.sql';
END $$;
COMMIT;
