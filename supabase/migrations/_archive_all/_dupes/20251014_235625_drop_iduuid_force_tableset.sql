DO $$
BEGIN
DECLARE
  r RECORD;
  attnum int;
  idx RECORD;
  con RECORD;
  tbls text[] := ARRAY[
    'clutch_plans',
    'clutches',
    'containers',
    'cross_instances',
    'crosses',
    'fish',
    'planned_crosses'
  ];
BEGIN
  FOREACH r IN ARRAY (
    SELECT unnest(tbls) AS tbl
  )
  LOOP
    SELECT a.attnum
      INTO attnum
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname='public'
      AND c.relname=r.tbl
      AND a.attname='id_uuid'
      AND a.attisdropped = false;

    IF attnum IS NULL THEN
      RAISE NOTICE 'Table public.% has no id_uuid column, skipping', r.tbl;
      CONTINUE;
    END IF;

    FOR con IN
      SELECT conname
      FROM pg_constraint
      WHERE conrelid = format('public.%I', r.tbl)::regclass
        AND (conkey IS NOT NULL)
        AND attnum = ANY (conkey)
    LOOP
      EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT IF EXISTS %I', r.tbl, con.conname);
      RAISE NOTICE 'Dropped constraint % on public.%', con.conname, r.tbl;
    END LOOP;

    FOR idx IN
      SELECT c2.relname AS idxname
      FROM pg_index i
      JOIN pg_class c1 ON c1.oid = i.indrelid
      JOIN pg_class c2 ON c2.oid = i.indexrelid
      JOIN pg_namespace n ON n.oid = c1.relnamespace
      WHERE n.nspname='public'
        AND c1.relname=r.tbl
        AND attnum = ANY (i.indkey)
    LOOP
      EXECUTE format('DROP INDEX IF EXISTS public.%I', idx.idxname);
      RAISE NOTICE 'Dropped index % on public.%', idx.idxname, r.tbl;
    END LOOP;

    BEGIN
      EXECUTE format('ALTER TABLE public.%I DROP COLUMN id_uuid', r.tbl);
      RAISE NOTICE 'Dropped column id_uuid on public.%', r.tbl;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'Could not drop public.%.id_uuid: %', r.tbl, SQLERRM;
    END;
  END LOOP;
END;
END;
$$ LANGUAGE plpgsql;
