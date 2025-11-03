BEGIN;
/*
  Rebuild-safe patch:
  This migration previously dropped legacy JCT columns and rebuilt views.
  Those actions are superseded by later normalized migrations.
  Keep this as a no-op so full rebuilds are deterministic.
*/
DO $$ BEGIN RAISE NOTICE '185430: legacy clutch drop/rebuild skipped (superseded)'; END $$;
COMMIT;
