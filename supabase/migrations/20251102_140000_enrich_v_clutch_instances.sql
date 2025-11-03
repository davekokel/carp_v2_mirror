BEGIN;
/* Rebuild-safe: legacy v_clutch_instances enrich skipped (superseded by v_clutch_instances_base + resolver) */
DO $$ BEGIN
  RAISE NOTICE 'legacy v_clutch_instances enrich skipped';
END $$;
COMMIT;
