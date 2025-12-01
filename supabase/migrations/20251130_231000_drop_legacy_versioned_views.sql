BEGIN;

DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT schemaname, viewname
    FROM pg_views
    WHERE schemaname = 'public'
      AND (
        viewname LIKE 'v7_%'
        OR viewname LIKE 'v8_%'
        OR viewname LIKE 'v9_%'
        OR viewname LIKE 'v10_%'
      )
  LOOP
    RAISE NOTICE 'Dropping legacy view: %.%', r.schemaname, r.viewname;
    EXECUTE format('DROP VIEW IF EXISTS %I.%I CASCADE;', r.schemaname, r.viewname);
  END LOOP;
END $$;

COMMIT;
