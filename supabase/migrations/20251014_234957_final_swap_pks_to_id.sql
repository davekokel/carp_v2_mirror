DO $$
DECLARE r record; pkname text;
BEGIN
  FOR r IN
    SELECT n.nspname AS sch, c.relname AS tbl
    FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace AND n.nspname='public'
    JOIN pg_index i ON i.indrelid=c.oid AND i.indisprimary
    JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=ANY(i.indkey)
    WHERE a.attname='id_uuid'
  LOOP
    IF NOT EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema=r.sch AND table_name=r.tbl AND column_name='id'
    ) THEN
      EXECUTE format('ALTER TABLE %I.%I ADD COLUMN id uuid', r.sch, r.tbl);
      EXECUTE format('UPDATE %I.%I SET id = id_uuid WHERE id IS NULL', r.sch, r.tbl);
      EXECUTE format('ALTER TABLE %I.%I ALTER COLUMN id SET NOT NULL', r.sch, r.tbl);
      EXECUTE format('ALTER TABLE %I.%I ALTER COLUMN id SET DEFAULT gen_random_uuid()', r.sch, r.tbl);
    END IF;

    SELECT conname INTO pkname
    FROM pg_constraint
    WHERE contype='p' AND conrelid=(quote_ident(r.sch)||'.'||quote_ident(r.tbl))::regclass;

    IF pkname IS NOT NULL THEN
      EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT %I', r.sch, r.tbl, pkname);
    END IF;

    EXECUTE format('ALTER TABLE %I.%I ADD CONSTRAINT %I PRIMARY KEY (id)', r.sch, r.tbl, r.tbl||'_pkey');
  END LOOP;
END $$;
