BEGIN;
DO $$
BEGIN
  RAISE NOTICE 'Skipping redundant v_clutch_instances_display labels migration: view already at stable shape (see 20251028_151603 baseline).';
END $$;
COMMIT;
