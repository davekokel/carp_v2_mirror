BEGIN;

DO $$
DECLARE r record;
BEGIN
  -- Drop legacy views in public schema
  FOR r IN
    SELECT schemaname, viewname
    FROM pg_views
    WHERE schemaname = 'public'
      AND viewname LIKE 'legacy_%'
  LOOP
    EXECUTE format('DROP VIEW IF EXISTS %I.%I CASCADE;', r.schemaname, r.viewname);
  END LOOP;
END $$;

DO $$
DECLARE r record;
BEGIN
  -- Drop legacy tables in public schema
  FOR r IN
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name LIKE 'legacy_%'
  LOOP
    EXECUTE format('DROP TABLE IF EXISTS %I.%I CASCADE;', r.table_schema, r.table_name);
  END LOOP;
END $$;

COMMIT;
