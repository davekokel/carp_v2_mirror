DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.relname AS tbl
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=c.relname AND column_name='id_uuid')
      AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=c.relname AND column_name='id')
    ORDER BY 1
  LOOP
    BEGIN
      EXECUTE format('ALTER TABLE public.%I DROP COLUMN id_uuid', r.tbl);
      RAISE NOTICE 'Dropped public.%.id_uuid', r.tbl;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'Skip public.%.id_uuid (still has deps): %', r.tbl, SQLERRM;
    END;
  END LOOP;
END $$;
