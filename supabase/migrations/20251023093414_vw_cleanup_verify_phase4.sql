BEGIN;

-- Drop any remaining vw_* views if they still exist
DO $$
DECLARE
  rec record;
BEGIN
  FOR rec IN
    SELECT n.nspname, c.relname
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind='v' AND n.nspname='public' AND c.relname LIKE 'vw\_%'
  LOOP
    EXECUTE format('DROP VIEW IF EXISTS %I.%I CASCADE;', rec.nspname, rec.relname);
  END LOOP;
END$$;

-- Confirm the schema is now free of vw_* aliases
RAISE NOTICE 'Remaining vw_* views: %',
  (SELECT json_agg(relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE c.relkind='v' AND n.nspname='public' AND c.relname LIKE 'vw\_%');

COMMIT;
