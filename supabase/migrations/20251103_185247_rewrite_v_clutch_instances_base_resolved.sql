BEGIN;
/*
  Rebuild-safe patch:
  This migration previously rewired v_clutch_instances_base_resolved.
  That view is superseded by v_clutch_instances_base + v_join_clutch_treatments_resolved.
  Keep this as a no-op so full rebuilds are deterministic.
*/
DO $$ BEGIN RAISE NOTICE '185247: v_clutch_instances_base_resolved rewrite skipped (superseded)'; END $$;
COMMIT;
