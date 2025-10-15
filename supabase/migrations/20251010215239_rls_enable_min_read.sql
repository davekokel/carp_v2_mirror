DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_schema='public' AND table_type='BASE TABLE'
  LOOP
    -- enable RLS
    EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', r.table_schema, r.table_name);

    -- add a blanket read policy for authenticated (idempotent)
    IF NOT EXISTS (
      SELECT 1 FROM pg_policy
      WHERE schemaname = r.table_schema
        AND tablename  = r.table_name
        AND polname = 'allow_read_auth'
    ) THEN
      EXECUTE format(
        'CREATE POLICY allow_read_auth ON %I.%I FOR SELECT TO authenticated USING (true)',
        r.table_schema, r.table_name
      );
    END IF;
  END LOOP;
END$$;
