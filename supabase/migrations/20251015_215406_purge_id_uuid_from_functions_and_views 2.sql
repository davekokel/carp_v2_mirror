do $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT p.oid
    FROM pg_catalog.pg_proc AS p
    JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.prokind IN ('f', 'p')
      AND pg_catalog.pg_get_functiondef(p.oid) ILIKE '%id_uuid%'
  LOOP
    EXECUTE replace(pg_catalog.pg_get_functiondef(r.oid), 'id_uuid', 'id');
  END LOOP;

  FOR r IN
    SELECT schemaname, viewname, definition
    FROM pg_views  WHERE schemaname = 'public' AND definition ILIKE '%id_uuid%'
  LOOP
    EXECUTE format(
      'CREATE OR REPLACE VIEW %I.%I AS %s',
      r.schemaname, r.viewname, replace(r.definition, 'id_uuid', 'id')
    );
  END LOOP;
END$$;
